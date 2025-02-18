# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging
from math import ceil
import numpy as np
import torch
from collections import defaultdict
from typing import List, Tuple, Dict
import random
import json

from fairdiplomacy import pydipcc
from fairdiplomacy.agents.base_search_agent import num_orderable_units
from fairdiplomacy.agents.threaded_search_agent import ThreadedSearchAgent
from fairdiplomacy.models.consts import POWERS
from fairdiplomacy.utils.sampling import sample_p_dict
from fairdiplomacy.utils.timing_ctx import TimingCtx


Action = Tuple[str]  # a set of orders
Power = str


class CFRData:
    def __init__(self):
        self.power_plausible_orders: Dict[Power, List[Action]] = {}
        self.sigma: Dict[Tuple[Power, Action], float] = {}
        self.cum_sigma: Dict[Tuple[Power, Action], float] = defaultdict(float)
        self.cum_regrets: Dict[Tuple[Power, Action], float] = defaultdict(float)
        self.cum_utility: Dict[Action, float] = defaultdict(float)
        self.last_regrets: Dict[Tuple[Power, Action], float] = defaultdict(float)
        self.bp_sigma: Dict[Tuple[Power, Action], float] = defaultdict(float)


class SearchBotAgent(ThreadedSearchAgent):
    """One-ply cfr with model-sampled rollouts"""

    def __init__(
        self,
        *,
        n_rollouts,
        cache_rollout_results=False,
        enable_compute_nash_conv=False,
        n_plausible_orders,
        use_optimistic_cfr=True,
        use_final_iter=True,
        use_pruning=False,
        max_batch_size=700,
        average_n_rollouts=1,
        n_rollout_procs,
        max_actions_units_ratio=None,
        plausible_orders_req_size=None,
        bp_iters=0,
        bp_prob=0,
        reset_seed_on_rollout=False,
        loser_bp_value=0.0,
        loser_bp_iter=64,
        share_strategy=False,
        n_gpu=None,  # deprecated
        n_server_procs=None,  # deprecated
        postman_sync_batches=None,  # deprecated
        use_predicted_final_scores=None,  # deprecated
        **kwargs,
    ):
        super().__init__(**kwargs, n_rollout_procs=n_rollout_procs, max_batch_size=max_batch_size)

        self.n_rollouts = n_rollouts
        self.cache_rollout_results = cache_rollout_results
        self.enable_compute_nash_conv = enable_compute_nash_conv
        self.n_plausible_orders = n_plausible_orders
        self.use_optimistic_cfr = use_optimistic_cfr
        self.use_final_iter = use_final_iter
        self.use_pruning = use_pruning
        self.plausible_orders_req_size = plausible_orders_req_size or max_batch_size
        self.average_n_rollouts = average_n_rollouts
        self.max_actions_units_ratio = (
            max_actions_units_ratio
            if max_actions_units_ratio is not None and max_actions_units_ratio > 0
            else 1e6
        )
        self.bp_iters = bp_iters
        self.bp_prob = bp_prob
        self.loser_bp_iter = loser_bp_iter
        self.loser_bp_value = loser_bp_value
        self.share_strategy = share_strategy

        self.reset_seed_on_rollout = reset_seed_on_rollout

        logging.info(f"Initialized SearchBotAgent: {self.__dict__}")

    def get_orders(self, game, power) -> List[str]:
        prob_distributions = self.get_all_power_prob_distributions(
            game, early_exit_for_power=power
        )
        logging.info(f"Final strategy: {prob_distributions[power]}")
        if len(prob_distributions[power]) == 0:
            return []
        return list(sample_p_dict(prob_distributions[power]))

    def get_orders_many_powers(
        self, game, powers, timings=None, single_cfr=None
    ) -> Dict[Power, List[str]]:

        if timings is None:
            timings = TimingCtx()
        if single_cfr is None:
            single_cfr = self.share_strategy
        with timings("get_orders_many_powers"):
            # Noop to differentiate from single power call.
            pass
        prob_distributions = {}
        if single_cfr:
            inner_timings = TimingCtx()
            prob_distributions = self.get_all_power_prob_distributions(game, timings=inner_timings)
            timings += inner_timings
        else:
            for power in powers:
                inner_timings = TimingCtx()
                prob_distributions[power] = self.get_all_power_prob_distributions(
                    game, early_exit_for_power=power, timings=inner_timings
                )[power]
                timings += inner_timings
        all_orders: Dict[Power, List[str]] = {}
        for power in powers:
            logging.info(f"Final strategy ({power}): {prob_distributions[power]}")
            if len(prob_distributions[power]) == 0:
                all_orders[power] = []
            else:
                all_orders[power] = list(sample_p_dict(prob_distributions[power]))
        timings.pprint(logging.getLogger("timings").info)
        return all_orders

    def get_plausible_orders_helper(self, game):
        # Determine the set of plausible actions to consider for each power
        game_state = game.get_state()
        power_n_units = [num_orderable_units(game_state, p) for p in POWERS]
        return self.get_plausible_orders(
            game,
            limit=[
                min(self.n_plausible_orders, ceil(u * self.max_actions_units_ratio))
                for u in power_n_units
            ],
            n=self.plausible_orders_req_size,
            batch_size=self.plausible_orders_req_size,
        )

    def get_all_power_prob_distributions(
        self,
        game,
        power_plausible_orders=None,
        early_exit_for_power=None,
        timings=None,
        extra_plausible_orders=None,
    ) -> Dict[str, Dict[Tuple[str], float]]:
        """Return dict {power: {action: prob}}"""

        if timings is None:
            timings = TimingCtx()
        timings.start("one-time")

        cfr_data = CFRData()

        game_state = game.get_state()
        phase = game_state["name"]

        if self.cache_rollout_results:
            rollout_results_cache = RolloutResultsCache()

        if power_plausible_orders is None:
            power_plausible_orders = self.get_plausible_orders_helper(game)

        if extra_plausible_orders:
            for p, orders in extra_plausible_orders.items():
                power_plausible_orders[p].update({order: 1.0 for order in orders})
                logging.info(f"Adding extra plausible orders {p}: {orders}")

        for p, orders_to_logprob in power_plausible_orders.items():
            for o, prob in orders_to_logprob.items():
                cfr_data.bp_sigma[(p, o)] = float(np.exp(prob))

        cfr_data.power_plausible_orders = {
            p: sorted(list(v.keys())) for p, v in power_plausible_orders.items()
        }
        del power_plausible_orders

        # If there are <=1 plausible orders, no need to search
        if (
            early_exit_for_power
            and len(cfr_data.power_plausible_orders[early_exit_for_power]) == 0
        ):
            return {early_exit_for_power: {tuple(): 1.0}}
        if (
            early_exit_for_power
            and len(cfr_data.power_plausible_orders[early_exit_for_power]) == 1
        ):
            return {
                early_exit_for_power: {
                    tuple(list(cfr_data.power_plausible_orders[early_exit_for_power]).pop()): 1.0
                }
            }

        if self.enable_compute_nash_conv:
            logging.info(f"Computing nash conv for blueprint")
            for temperature in (1.0, 0.5, 0.1, 0.01):
                self.compute_nash_conv(
                    cfr_data,
                    f"blueprint T={temperature}",
                    game,
                    lambda cfr_data, power: self.bp_strategy(
                        cfr_data, power, temperature=temperature
                    ),
                )

        iter_weight = 0.0
        for cfr_iter in range(self.n_rollouts):
            timings.start("start")
            # do verbose logging on 2^x iters
            verbose_log_iter = (
                cfr_iter & (cfr_iter + 1) == 0  # and cfr_iter > self.n_rollouts / 8
            ) or cfr_iter == self.n_rollouts - 1

            self.maybe_do_pruning(cfr_iter=cfr_iter, iter_weight=iter_weight, cfr_data=cfr_data)

            iter_weight = self.linear_cfr(cfr_data, cfr_iter, iter_weight)

            timings.start("query_policy")
            # get policy probs for all powers
            power_is_loser = {
                pwr: self.is_loser(cfr_data, pwr, cfr_iter, actions, iter_weight)
                for (pwr, actions) in cfr_data.power_plausible_orders.items()
            }
            power_action_ps: Dict[Power, List[float]] = {
                pwr: (
                    self.bp_strategy(cfr_data, pwr)
                    if (
                        cfr_iter < self.bp_iters
                        or np.random.rand() < self.bp_prob
                        or power_is_loser[pwr]
                    )
                    else self.strategy(cfr_data, pwr)
                )
                for (pwr, actions) in cfr_data.power_plausible_orders.items()
            }

            timings.start("apply_orders")
            # sample policy for all powers
            idxs = {
                pwr: np.random.choice(range(len(action_ps)), p=action_ps)
                for pwr, action_ps in power_action_ps.items()
                if len(action_ps) > 0
            }
            power_sampled_orders: Dict[Power, Tuple[Action, float]] = {
                pwr: (
                    (cfr_data.power_plausible_orders[pwr][idxs[pwr]], action_ps[idxs[pwr]])
                    if pwr in idxs
                    else ((), 1.0)
                )
                for pwr, action_ps in power_action_ps.items()
            }

            # for each power: compare all actions against sampled opponent action
            set_orders_dicts = [
                {**{p: a for p, (a, _) in power_sampled_orders.items()}, pwr: action}
                for pwr, actions in cfr_data.power_plausible_orders.items()
                for action in actions
            ]

            # run rollouts or get from cache
            def on_miss():
                nonlocal timings
                inner_timmings = TimingCtx()
                ret = self.do_rollouts(
                    game,
                    set_orders_dicts,
                    average_n_rollouts=self.average_n_rollouts,
                    timings=inner_timmings,
                    log_timings=verbose_log_iter,
                )
                timings += inner_timmings
                return ret

            timings.stop()
            all_rollout_results = (
                rollout_results_cache.get(set_orders_dicts, on_miss)
                if self.cache_rollout_results
                else on_miss()
            )

            timings.start("cfr")
            for pwr, actions in cfr_data.power_plausible_orders.items():
                if len(actions) == 0:
                    continue

                # pop this power's results
                results, all_rollout_results = (
                    all_rollout_results[: len(actions)],
                    all_rollout_results[len(actions) :],
                )

                # calculate regrets
                action_utilities: List[float] = [r[1][pwr] for r in results]
                state_utility = np.dot(power_action_ps[pwr], action_utilities)
                action_regrets = [(u - state_utility) for u in action_utilities]

                # log some action values
                if verbose_log_iter:
                    self.log_cfr_iter_state(
                        game=game,
                        pwr=pwr,
                        actions=actions,
                        cfr_data=cfr_data,
                        cfr_iter=cfr_iter,
                        iter_weight=iter_weight,
                        power_is_loser=power_is_loser,
                        state_utility=state_utility,
                        action_utilities=action_utilities,
                    )

                # update cfr data structures
                self.update_cfr_data(
                    cfr_data, pwr, actions, state_utility, action_utilities, action_regrets
                )

            if self.enable_compute_nash_conv and verbose_log_iter:
                logging.info(f"Computing nash conv for iter {cfr_iter}")
                self.compute_nash_conv(cfr_data, f"cfr iter {cfr_iter}", game, self.avg_strategy)

            if self.cache_rollout_results and (cfr_iter + 1) % 10 == 0:
                logging.info(f"{rollout_results_cache}")

        timings.start("to_dict")

        # return prob. distributions for each power
        ret = {}
        for p in POWERS:
            final_ps = self.strategy(cfr_data, p)
            avg_ps = self.avg_strategy(cfr_data, p)
            bp_ps = self.bp_strategy(cfr_data, p)
            ps = bp_ps if power_is_loser[p] else (final_ps if self.use_final_iter else avg_ps)
            ret[p] = dict(
                sorted(zip(cfr_data.power_plausible_orders[p], ps), key=lambda ac_p: -ac_p[1])
            )

            if early_exit_for_power == p:
                avg_ps_dict = dict(
                    sorted(
                        zip(cfr_data.power_plausible_orders[p], avg_ps), key=lambda ac_p: -ac_p[1]
                    )
                )
                logging.info(f"Final avg strategy: {avg_ps_dict}")

        timings.pprint(logging.getLogger("timings").info)
        return ret

    @classmethod
    def strategy(cls, cfr_data, power) -> List[float]:
        actions = cfr_data.power_plausible_orders[power]
        try:
            return [cfr_data.sigma[(power, a)] for a in actions]
        except KeyError:
            return [1.0 / len(actions) for _ in actions]

    @classmethod
    def avg_strategy(cls, cfr_data, power) -> List[float]:
        actions = cfr_data.power_plausible_orders[power]
        sigmas = [cfr_data.cum_sigma[(power, a)] for a in actions]
        sum_sigmas = sum(sigmas)
        if sum_sigmas == 0:
            return [1 / len(actions) for _ in actions]
        else:
            return [s / sum_sigmas for s in sigmas]

    @classmethod
    def bp_strategy(cls, cfr_data, power, temperature=1.0) -> List[float]:
        actions = cfr_data.power_plausible_orders[power]
        sigmas = [cfr_data.bp_sigma[(power, a)] ** (1.0 / temperature) for a in actions]
        sum_sigmas = sum(sigmas)
        assert len(actions) == 0 or sum_sigmas > 0, f"{actions} {cfr_data.bp_sigma}"
        return [s / sum_sigmas for s in sigmas]

    def update_cfr_data(
        self, cfr_data, pwr, actions, state_utility, action_utilities, action_regrets
    ):
        sigmas = self.strategy(cfr_data, pwr)
        for action, regret, s in zip(actions, action_regrets, sigmas):
            cfr_data.cum_regrets[(pwr, action)] += regret
            cfr_data.last_regrets[(pwr, action)] = regret
            cfr_data.cum_sigma[(pwr, action)] += s
        cfr_data.cum_utility[pwr] += state_utility

        if self.use_optimistic_cfr:
            pos_regrets = [
                max(0, cfr_data.cum_regrets[(pwr, a)] + cfr_data.last_regrets[(pwr, a)])
                for a in actions
            ]
        else:
            pos_regrets = [max(0, cfr_data.cum_regrets[(pwr, a)]) for a in actions]

        sum_pos_regrets = sum(pos_regrets)
        for action, pos_regret in zip(actions, pos_regrets):
            if sum_pos_regrets == 0:
                cfr_data.sigma[(pwr, action)] = 1.0 / len(actions)
            else:
                cfr_data.sigma[(pwr, action)] = pos_regret / sum_pos_regrets

    def maybe_do_pruning(self, *, cfr_iter, **kwargs):
        if not self.use_pruning:
            return

        if cfr_iter == 1 + int(self.n_rollouts / 4):
            self.prune_actions(
                cfr_iter=cfr_iter, ave_regret_thresh=-0.06, ave_strat_thresh=0.002, **kwargs
            )

        if cfr_iter == 1 + int(self.n_rollouts / 2):
            self.prune_actions(
                cfr_iter=cfr_iter, ave_regret_thresh=-0.03, ave_strat_thresh=0.001, **kwargs
            )

    @classmethod
    def prune_actions(
        cls, *, cfr_iter, iter_weight, cfr_data, ave_regret_thresh, ave_strat_thresh
    ):
        for pwr, actions in cfr_data.power_plausible_orders.items():
            paired_list = []
            for action in actions:
                ave_regret = cfr_data.cum_regrets[(pwr, action)] / iter_weight
                new_pair = (action, ave_regret)
                paired_list.append(new_pair)
            paired_list.sort(key=lambda tup: tup[1])
            for (action, ave_regret) in paired_list:
                ave_strat = cfr_data.cum_sigma[(pwr, action)] / iter_weight
                if (
                    ave_regret < ave_regret_thresh
                    and ave_strat < ave_strat_thresh
                    and cfr_data.sigma[(pwr, action)] == 0
                ):
                    cfr_data.cum_sigma[(pwr, action)] = 0
                    logging.info(
                        "pruning on iter {} action {} with ave regret {} and ave strat {}".format(
                            cfr_iter, action, ave_regret, ave_strat
                        )
                    )
                    actions.remove(action)

    @classmethod
    def linear_cfr(cls, cfr_data, cfr_iter, iter_weight) -> float:
        discount_factor = (cfr_iter + 0.000001) / (cfr_iter + 1)

        for pwr, actions in cfr_data.power_plausible_orders.items():
            if len(actions) == 0:
                continue
            cfr_data.cum_utility[pwr] *= discount_factor
            for action in actions:
                cfr_data.cum_regrets[(pwr, action)] *= discount_factor
                cfr_data.cum_sigma[(pwr, action)] *= discount_factor

        return iter_weight * discount_factor + 1.0

    def log_cfr_iter_state(
        self,
        *,
        game,
        pwr,
        actions,
        cfr_data,
        cfr_iter,
        iter_weight,
        power_is_loser,
        state_utility,
        action_utilities,
    ):
        logging.info(
            f"<> [ {cfr_iter+1} / {self.n_rollouts} ] {pwr} {game.phase} avg_utility={cfr_data.cum_utility[pwr] / iter_weight:.5f} cur_utility={state_utility:.5f} "
            f"is_loser= {int(power_is_loser[pwr])}"
        )
        logging.info(f"     {'probs':8s}  {'bp_p':8s}  {'avg_u':8s}  {'cur_u':8s}  orders")
        action_probs: List[float] = self.avg_strategy(cfr_data, pwr)
        bp_probs: List[float] = self.bp_strategy(cfr_data, pwr)
        avg_utilities = [
            (cfr_data.cum_regrets[(pwr, a)] + cfr_data.cum_utility[pwr]) / iter_weight
            for a in actions
        ]
        sorted_metrics = sorted(
            zip(actions, action_probs, bp_probs, avg_utilities, action_utilities),
            key=lambda ac: -ac[1],
        )
        for orders, p, bp_p, avg_u, cur_u in sorted_metrics:
            logging.info(f"|>  {p:8.5f}  {bp_p:8.5f}  {avg_u:8.5f}  {cur_u:8.5f}  {orders}")

    def compute_nash_conv(self, cfr_data, label, game, strat_f):
        """For each power, compute EV of each action assuming opponent ave policies"""

        # get policy probs for all powers
        power_action_ps: Dict[Power, List[float]] = {
            pwr: strat_f(cfr_data, pwr)
            for (pwr, actions) in cfr_data.power_plausible_orders.items()
        }
        logging.info("Policies: {}".format(power_action_ps))

        total_action_utilities: Dict[Tuple[Power, Action], float] = defaultdict(float)
        temp_action_utilities: Dict[Tuple[Power, Action], float] = defaultdict(float)
        total_state_utility: Dict[Power, float] = defaultdict(float)
        max_state_utility: Dict[Power, float] = defaultdict(float)
        for pwr, actions in cfr_data.power_plausible_orders.items():
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
                    (cfr_data.power_plausible_orders[pwr][idxs[pwr]], action_ps[idxs[pwr]])
                    if pwr in idxs
                    else ((), 1.0)
                )
                for pwr, action_ps in power_action_ps.items()
            }

            # for each power: compare all actions against sampled opponent action
            set_orders_dicts = [
                {**{p: a for p, (a, _) in power_sampled_orders.items()}, pwr: action}
                for pwr, actions in cfr_data.power_plausible_orders.items()
                for action in actions
            ]
            all_rollout_results = self.do_rollouts(
                game, set_orders_dicts, average_n_rollouts=self.average_n_rollouts
            )

            for pwr, actions in cfr_data.power_plausible_orders.items():
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
                # for i in range(len(cfr_data.power_plausible_orders[pwr])):
                #     action = cfr_data.power_plausible_orders[pwr][i]
                #     util = action_utilities[i]
                #     logging.info("{} {} = {}".format(pwr,action,util))

                # for action in cfr_data.power_plausible_orders[pwr]:
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
        for pwr, actions in cfr_data.power_plausible_orders.items():
            # ps = self.avg_strategy(pwr, cfr_data.power_plausible_orders[pwr])
            for i in range(len(actions)):
                action = actions[i]
                total_action_utilities[(pwr, action)] /= br_iters
                if total_action_utilities[(pwr, action)] > max_state_utility[pwr]:
                    max_state_utility[pwr] = total_action_utilities[(pwr, action)]
                total_state_utility[pwr] += (
                    total_action_utilities[(pwr, action)] * power_action_ps[pwr][i]
                )

        for pwr, actions in cfr_data.power_plausible_orders.items():
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

        logging.info(f"Nash conv for {label} = {nash_conv}")

    def is_loser(self, cfr_data, pwr, cfr_iter, plausible_orders, iter_weight):
        if cfr_iter >= self.loser_bp_iter and self.loser_bp_value > 0:
            for action in plausible_orders:
                if (
                    cfr_data.cum_regrets[(pwr, action)] + cfr_data.cum_utility[pwr]
                ) / iter_weight > self.loser_bp_value:
                    return False
            return True
        return False


class RolloutResultsCache:
    def __init__(self):
        self.cache = {}
        self.hits = 0
        self.misses = 0

    def get(self, set_orders_dicts, onmiss_fn):
        key = frozenset(frozenset(d.items()) for d in set_orders_dicts)
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        else:
            self.misses += 1
            r = onmiss_fn()
            self.cache[key] = r
            return r

    def __repr__(self):
        return "RolloutResultsCache[{} / {} = {:.3f}]".format(
            self.hits, self.hits + self.misses, self.hits / (self.hits + self.misses)
        )


if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s [%(levelname)s]: %(message)s", level=logging.INFO)

    np.random.seed(0)
    torch.manual_seed(0)

    game = pydipcc.Game()

    agent = SearchBotAgent(
        n_rollouts=10,
        max_rollout_length=3,
        model_path="/checkpoint/alerer/fairdiplomacy/sl_fbdata_all/checkpoint.pth.best",
        rollout_temperature=0.5,
        n_rollout_procs=24 * 7,
        rollout_top_p=0.9,
        mix_square_ratio_scoring=0.1,
        n_plausible_orders=8,
        average_n_rollouts=3,
    )
    print(agent.get_orders(game, "AUSTRIA"))
