# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging
from math import ceil
import numpy as np
import torch
from collections import defaultdict, OrderedDict
from typing import List, Tuple, Dict, Set

from fairdiplomacy.agents.multiproc_search_agent import MultiprocSearchAgent
from fairdiplomacy.models.consts import POWERS
from fairdiplomacy.utils.timing_ctx import TimingCtx
from fairdiplomacy.utils.sampling import sample_p_dict


Action = Tuple[str]  # a set of orders
Power = str
Policy = List[Tuple[Action, float]]
JointPolicy = Dict[Power, Policy]


class FP1PAgent(MultiprocSearchAgent):
    """One-ply fictitious play with model-sampled policy rollouts"""

    def __init__(
        self,
        *,
        n_rollouts,
        cache_rollout_results=0,
        enable_compute_nash_conv=False,
        n_plausible_orders,
        postman_sync_batches=False,
        # use_optimistic_cfr=True,
        use_final_iter=True,
        # use_pruning=False,
        max_batch_size=700,
        average_n_rollouts=1,
        n_rollout_procs,
        max_actions_units_ratio=None,
        plausible_orders_req_size=None,
        bp_iters=0,
        bp_prob=0,
        **kwargs,
    ):
        super().__init__(
            **kwargs,
            n_rollout_procs=(
                n_plausible_orders * len(POWERS) if postman_sync_batches else n_rollout_procs
            ),
            max_batch_size=(
                n_plausible_orders * len(POWERS) if postman_sync_batches else max_batch_size
            ),
            postman_wait_till_full=postman_sync_batches,
        )

        if postman_sync_batches:
            assert n_rollout_procs >= n_plausible_orders * len(POWERS)

        self.n_rollouts = n_rollouts
        self.cache_rollout_results = cache_rollout_results
        self.enable_compute_nash_conv = enable_compute_nash_conv
        self.n_plausible_orders = n_plausible_orders
        self.postman_sync_batches = postman_sync_batches
        self.use_final_iter = use_final_iter
        # self.use_pruning = use_pruning
        self.plausible_orders_req_size = plausible_orders_req_size or max_batch_size
        self.average_n_rollouts = average_n_rollouts
        self.max_actions_units_ratio = (
            max_actions_units_ratio
            if max_actions_units_ratio is not None and max_actions_units_ratio > 0
            else 1e6
        )
        self.bp_iters = bp_iters
        self.bp_prob = bp_prob

        logging.info(f"Initialized FP1P Agent: {self.__dict__}")

    def get_orders(self, game, power) -> Action:
        prob_distributions = self.get_all_power_prob_distributions(
            game, early_exit_for_power=power
        )
        logging.info(f"Final strategy: {prob_distributions[power]}")
        if len(prob_distributions[power]) == 0:
            return []
        return list(sample_p_dict(prob_distributions[power]))

    def get_all_power_prob_distributions(self, game, early_exit_for_power=None) -> JointPolicy:
        """Return dict {power: {action: prob}}"""

        # CFR data structures
        self.cum_utility = defaultdict(float)
        self.cum_sigma = defaultdict(float)

        game_state = game.get_state()
        phase = game_state["name"]

        if self.cache_rollout_results:
            rollout_results_cache = RolloutResultsCache(min_count=self.cache_rollout_results)

        if self.postman_sync_batches:
            self.client.set_batch_size(torch.LongTensor([self.plausible_orders_req_size]))

        # Determine the set of plausible actions to consider for each power
        power_n_units = [num_orderable_units(game_state, p) for p in POWERS]
        plausible_order_dicts = self.get_plausible_orders(
            game,
            limit=[
                min(self.n_plausible_orders, ceil(u * self.max_actions_units_ratio))
                for u in power_n_units
            ],
            n=self.plausible_orders_req_size,
            batch_size=self.plausible_orders_req_size,
        )
        power_plausible_orders: Dict[Power, List[Action]] = {
            p: list(v.keys()) for p, v in plausible_order_dicts.items()
        }
        bp_policy: Dict[Power, List[float]] = {
            pwr: [np.exp(float(od[o])) for o in power_plausible_orders[pwr]]
            for pwr, od in plausible_order_dicts.items()
        }
        # normalize everything
        bp_policy = {pwr: [p / sum(probs) for p in probs] for pwr, probs in bp_policy.items()}

        logging.debug(f"{phase} power_plausible_orders: {power_plausible_orders}")

        if self.postman_sync_batches:
            self.client.set_batch_size(
                torch.LongTensor([sum(map(len, power_plausible_orders.values()))])
            )

        if early_exit_for_power and len(power_plausible_orders[early_exit_for_power]) == 0:
            return {early_exit_for_power: {tuple(): 1.0}}
        if early_exit_for_power and len(power_plausible_orders[early_exit_for_power]) == 1:
            return {
                early_exit_for_power: {
                    tuple(list(power_plausible_orders[early_exit_for_power]).pop()): 1.0
                }
            }

        timings = TimingCtx()
        assert self.bp_iters > 0
        for fp_iter in range(self.n_rollouts):

            # if self.use_pruning and fp_iter == 1 + int(self.n_rollouts / 4):
            #     for pwr, actions in power_plausible_orders.items():
            #         paired_list = []
            #         for action in actions:
            #             ave_regret = self.cum_regrets[(pwr, action)] / iter_weight
            #             new_pair = (action, ave_regret)
            #             paired_list.append(new_pair)
            #         paired_list.sort(key=lambda tup: tup[1])
            #         for (action, ave_regret) in paired_list:
            #             ave_strat = self.cum_sigma[(pwr, action)] / iter_weight
            #             if (
            #                 ave_regret < -0.06
            #                 and ave_strat < 0.002
            #                 and self.sigma[(pwr, action)] == 0
            #             ):
            #                 self.cum_sigma[(pwr, action)] = 0
            #                 logging.info(
            #                     "pruning on iter {} action {} with ave regret {} and ave strat {}".format(
            #                         fp_iter, action, ave_regret, ave_strat
            #                     )
            #                 )
            #                 actions.remove(action)

            # print('bp_policy')
            # print(bp_policy)
            if fp_iter < self.bp_iters or np.random.rand() < self.bp_prob:
                action_idxs: Dict[Power, int] = {
                    pwr: np.random.choice(range(len(probs)), p=probs)
                    for pwr, probs in bp_policy.items()
                    if len(probs) > 0
                }
            else:
                action_idxs: Dict[Power, int] = {
                    pwr: np.argmax([self.cum_utility[(pwr, a)] for a in actions])
                    for pwr, actions in power_plausible_orders.items()
                    if len(actions) > 0
                }

            cur_policy: Dict[Power, Action] = {
                pwr: (power_plausible_orders[pwr][action_idxs[pwr]] if pwr in action_idxs else ())
                for pwr in POWERS
            }

            # update cum_sigma
            for power, action in cur_policy.items():
                self.cum_sigma[power, action] += 1

            # get payoffs for all actions vs cur_policy
            # for each power: compare all actions against sampled opponent action
            set_orders_dicts = [
                {**{p: a for p, a in cur_policy.items()}, pwr: action}
                for pwr, actions in power_plausible_orders.items()
                for action in actions
            ]

            # run rollouts or get from cache
            def on_miss():
                with timings("distribute_rollouts"):
                    return self.distribute_rollouts(
                        game, set_orders_dicts, average_n_rollouts=self.average_n_rollouts
                    )

            all_rollout_results = (
                rollout_results_cache.get(set_orders_dicts, on_miss)
                if self.cache_rollout_results
                else on_miss()
            )
            if fp_iter & (fp_iter + 1) == 0:  # 2^n-1
                logging.info(f"[{fp_iter+1}/{self.n_rollouts}] Power sampled orders:")
                for power, orders in cur_policy.items():
                    logging.info(f"    {power:10s}  {orders}")
                if self.cache_rollout_results:
                    logging.info(f"{rollout_results_cache}")

            for pwr, actions in power_plausible_orders.items():
                if len(actions) == 0:
                    continue

                # pop this power's results
                results, all_rollout_results = (
                    all_rollout_results[: len(actions)],
                    all_rollout_results[len(actions) :],
                )

                # calculate regrets
                action_utilities: List[float] = [r[1][pwr] for r in results]
                for action, utility in zip(actions, action_utilities):
                    self.cum_utility[(pwr, action)] += utility
                # state_utility = np.dot(power_action_ps[pwr], action_utilities)
                # action_regrets = [(u - state_utility) for u in action_utilities]

                # log some action values
                # if fp_iter & (fp_iter + 1) == 0:  # 2^n-1
                # if fp_iter == self.n_rollouts - 1:
                #     logging.info(f"[{fp_iter+1}/{self.n_rollouts}] {pwr} cum_utility={self.cum_utility[pwr] / iter_weight:.5f} cur_utility={state_utility:.5f}")
                #     logging.info(f"    {'probs':8s}  {'avg_u':8s}  {'cur_u':8s}  orders")
                #     action_probs: List[float] = self.avg_strategy(pwr, power_plausible_orders[pwr])
                #     avg_utilities = [(self.cum_regrets[(pwr, a)] + self.cum_utility[pwr]) / iter_weight for a in actions]
                #     sorted_metrics = sorted(zip(actions, action_probs, avg_utilities, action_utilities), key=lambda ac: -ac[2])
                #     for orders, p, avg_u, cur_u in sorted_metrics:
                #         logging.info(f"    {p:8.5f}  {avg_u:8.5f}  {cur_u:8.5f}  {orders}")

                # update cfr data structures
                # self.cum_utility[pwr] += state_utility
                # for action, regret, s in zip(actions, action_regrets, power_action_cfr[pwr]):
                #     self.cum_regrets[(pwr, action)] += regret
                #     self.last_regrets[(pwr, action)] = regret
                #     self.cum_sigma[(pwr, action)] += s

                # if self.use_optimistic_cfr:
                #     pos_regrets = [
                #         max(0, self.cum_regrets[(pwr, a)] + self.last_regrets[(pwr, a)])
                #         for a in actions
                #     ]
                # else:
                #     pos_regrets = [max(0, self.cum_regrets[(pwr, a)]) for a in actions]

                # sum_pos_regrets = sum(pos_regrets)
                # for action, pos_regret in zip(actions, pos_regrets):
                #     if sum_pos_regrets == 0:
                #         self.sigma[(pwr, action)] = 1.0 / len(actions)
                #     else:
                #         self.sigma[(pwr, action)] = pos_regret / sum_pos_regrets

            if self.enable_compute_nash_conv and fp_iter in (
                24,
                49,
                99,
                199,
                399,
                self.n_rollouts - 1,
            ):
                logging.info(f"Computing nash conv for iter {fp_iter}")
                self.compute_nash_conv(fp_iter, game, power_plausible_orders)

            logging.debug(
                f"Timing[fp_iter {fp_iter+1}/{self.n_rollouts}]: {str(timings)}, len(set_orders_dicts)={len(set_orders_dicts)}"
            )
            timings.clear()

        # return prob. distributions for each power
        ret = {
            pwr: {action: self.cum_sigma[(pwr, action)] / self.n_rollouts for action in actions}
            for pwr, actions in power_plausible_orders.items()
        }

        if early_exit_for_power is not None:
            logging.info(f"Final avg strategy: {ret[early_exit_for_power]}")

        return ret

    # def strategy(self, power, actions) -> List[float]:
    #     try:
    #         return [self.sigma[(power, a)] for a in actions]
    #     except KeyError:
    #         return [1.0 / len(actions) for _ in actions]

    def avg_strategy(self, power, actions) -> List[float]:
        sigmas = [self.cum_sigma[(power, a)] for a in actions]
        sum_sigmas = sum(sigmas)
        if sum_sigmas == 0:
            return [1 / len(actions) for _ in actions]
        else:
            return [s / sum_sigmas for s in sigmas]

    # def bp_strategy(self, power, actions) -> List[float]:
    #     sigmas = [self.bp_sigma[(power, a)] for a in actions]
    #     sum_sigmas = sum(sigmas)
    #     assert len(actions) == 0 or sum_sigmas > 0, f"{actions} {self.bp_sigma}"
    #     return [s / sum_sigmas for s in sigmas]

    def compute_nash_conv(self, fp_iter, game, power_plausible_orders):
        """For each power, compute EV of each action assuming opponent ave policies"""

        # get policy probs for all powers
        power_action_ps: Dict[Power, List[float]] = {
            pwr: self.avg_strategy(pwr, actions)
            for (pwr, actions) in power_plausible_orders.items()
        }
        logging.info("Policies: {}".format(power_action_ps))

        total_action_utilities: Dict[Tuple[Power, Action], float] = defaultdict(float)
        temp_action_utilities: Dict[Tuple[Power, Action], float] = defaultdict(float)
        total_state_utility: Dict[Power, float] = defaultdict(float)
        max_state_utility: Dict[Power, float] = defaultdict(float)
        for pwr, actions in power_plausible_orders.items():
            total_state_utility[pwr] = 0
            max_state_utility[pwr] = 0
        # total_state_utility = [0 for u in idxs]
        nash_conv = 0
        br_iters = 100
        for _ in range(br_iters):
            # sample policy for all powers
            idxs = {
                pwr: np.random.choice(range(len(action_ps)), p=action_ps)
                for pwr, action_ps in power_action_ps.items()
                if len(action_ps) > 0
            }
            power_sampled_orders: Dict[Power, Tuple[Action, float]] = {
                pwr: (
                    (power_plausible_orders[pwr][idxs[pwr]], action_ps[idxs[pwr]])
                    if pwr in idxs
                    else ((), 1.0)
                )
                for pwr, action_ps in power_action_ps.items()
            }

            # for each power: compare all actions against sampled opponent action
            set_orders_dicts = [
                {**{p: a for p, (a, _) in power_sampled_orders.items()}, pwr: action}
                for pwr, actions in power_plausible_orders.items()
                for action in actions
            ]
            all_rollout_results = self.distribute_rollouts(
                game, set_orders_dicts, average_n_rollouts=self.average_n_rollouts
            )

            for pwr, actions in power_plausible_orders.items():
                if len(actions) == 0:
                    continue

                # pop this power's results
                results, all_rollout_results = (
                    all_rollout_results[: len(actions)],
                    all_rollout_results[len(actions) :],
                )

                for r in results:
                    action = r[0][pwr]
                    val = r[1][pwr]
                    temp_action_utilities[(pwr, action)] = val
                    total_action_utilities[(pwr, action)] += val
                # logging.info("results for power={}".format(pwr))
                # for i in range(len(power_plausible_orders[pwr])):
                #     action = power_plausible_orders[pwr][i]
                #     util = action_utilities[i]
                #     logging.info("{} {} = {}".format(pwr,action,util))

                # for action in power_plausible_orders[pwr]:
                #     logging.info("{} {} = {}".format(pwr,action,action_utilities))
                # logging.info("action utilities={}".format(action_utilities))
                # logging.info("Results={}".format(results))
                # state_utility = np.dot(power_action_ps[pwr], action_utilities)
                # action_regrets = [(u - state_utility) for u in action_utilities]
                # logging.info("Action utilities={}".format(temp_action_utilities))
                # for action in actions:
                #     total_action_utilities[(pwr,action)] += temp_action_utilities[(pwr,action)]
                # logging.info("Total action utilities={}".format(total_action_utilities))
                # total_state_utility[pwr] += state_utility
        # total_state_utility[:] = [x / 100 for x in total_state_utility]
        for pwr, actions in power_plausible_orders.items():
            # ps = self.avg_strategy(pwr, power_plausible_orders[pwr])
            for i in range(len(actions)):
                action = actions[i]
                total_action_utilities[(pwr, action)] /= br_iters
                if total_action_utilities[(pwr, action)] > max_state_utility[pwr]:
                    max_state_utility[pwr] = total_action_utilities[(pwr, action)]
                total_state_utility[pwr] += (
                    total_action_utilities[(pwr, action)] * power_action_ps[pwr][i]
                )

        for pwr, actions in power_plausible_orders.items():
            logging.info(
                "results for power={} value={} diff={}".format(
                    pwr,
                    total_state_utility[pwr],
                    (max_state_utility[pwr] - total_state_utility[pwr]),
                )
            )
            nash_conv += max_state_utility[pwr] - total_state_utility[pwr]
            for i in range(len(actions)):
                action = actions[i]
                logging.info(
                    "{} {} = {} (prob {})".format(
                        pwr, action, total_action_utilities[(pwr, action)], power_action_ps[pwr][i]
                    )
                )

        logging.info(f"Nash conv for iter {fp_iter} = {nash_conv}")


def _map2(N1, N2, F):
    if isinstance(N1, list):
        return [_map2(n1, n2, F) for n1, n2 in zip(N1, N2)]
    elif isinstance(N1, tuple):
        return tuple(_map2(n1, n2, F) for n1, n2 in zip(N1, N2))
    elif isinstance(N1, dict):
        return {k: _map2(N1[k], N2[k], F) for k in N1}
    elif isinstance(N1, float):
        return F(N1, N2)
    else:
        if N1 != N2:
            raise RuntimeError(f"Error in _map2: {N1} != {N2}")
        return N1


class RolloutResultsCache:
    def __init__(self, min_count=4):
        self.cache_count = defaultdict(int)
        self.cache_avg = {}
        self.hits = 0
        self.misses = 0
        self.min_count = min_count

    def get(self, set_orders_dicts, onmiss_fn):
        key = frozenset(frozenset(d.items()) for d in set_orders_dicts)
        if self.cache_count[key] >= self.min_count:
            self.hits += 1
            return self.cache_avg[key]
        else:
            self.misses += 1
            r = onmiss_fn()
            try:
                self.cache_avg[key] = (
                    _map2(
                        self.cache_avg[key],
                        r,
                        lambda avg, sample: (avg * self.cache_count[key] + sample)
                        / (self.cache_count[key] + 1),
                    )
                    if key in self.cache_avg
                    else r
                )
                self.cache_count[key] += 1
            except RuntimeError as e:
                print(e)

            return r

    def __repr__(self):
        return "RolloutResultsCache[{} / {} = {:.3f}% hit]".format(
            self.hits, self.hits + self.misses, self.hits / (self.hits + self.misses) * 100
        )


def num_orderable_units(game_state, power):
    if game_state["name"][-1] == "A":
        return abs(game_state["builds"].get(power, {"count": 0})["count"])
    if game_state["name"][-1] == "R":
        return len(game_state["retreats"].get(power, []))
    else:
        return len(game_state["units"].get(power, []))


if __name__ == "__main__":
    from fairdiplomacy.pydipcc import Game

    logging.basicConfig(format="%(asctime)s [%(levelname)s]: %(message)s", level=logging.INFO)

    np.random.seed(0)
    torch.manual_seed(0)

    agent = FP1PAgent(
        n_rollouts=10,
        max_rollout_length=5,
        model_path="/checkpoint/alerer/fairdiplomacy/sl_value4_alpha0.9_nosm_vlw0.9/checkpoint.pth.best",
        postman_sync_batches=False,
        rollout_temperature=0.5,
        n_rollout_procs=24 * 7,
        rollout_top_p=0.9,
        mix_square_ratio_scoring=0.1,
        n_plausible_orders=24,
        average_n_rollouts=3,
        bp_iters=3,
    )
    print(agent.get_orders(Game(), "GERMANY"))
