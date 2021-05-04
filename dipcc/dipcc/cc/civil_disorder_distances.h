/*
Copyright (c) Facebook, Inc. and its affiliates.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
*/

#pragma once

#include <map>
#include <vector>

#include "power.h"

namespace dipcc {

// distances generated by TestGenCivilDisorder

const std::map<Power, std::vector<int>> CIVIL_DISORDER_DISTS_ARMY{

    {Power::AUSTRIA,
     {
         6, 6, 6, 7, 5, 6, 7, 6, 5, 6, 6, 4, 4, 4, 4, 5, 5, 5, 5, 5, 4,
         3, 3, 4, 3, 5, 5, 4, 4, 4, 4, 4, 5, 4, 4, 4, 4, 3, 2, 3, 4, 3,
         3, 4, 3, 3, 3, 3, 2, 1, 2, 1, 2, 2, 2, 2, 2, 3, 2, 1, 1, 0, 0,
         3, 2, 1, 1, 3, 1, 2, 3, 2, 0, 1, 3, 4, 4, 2, 2, 3, 2,
     }},
    {Power::ENGLAND,
     {
         1, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
         3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4,
         4, 3, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 6, 6, 6, 6,
         6, 6, 6, 6, 6, 6, 6, 6, 6, 7, 7, 7, 7, 7, 7, 7, 7, 7,
     }},
    {Power::FRANCE,
     {
         3, 3, 2, 3, 2, 2, 3, 3, 1, 2, 2, 2, 3, 3, 3, 3, 3, 4, 0, 1, 1,
         1, 2, 4, 3, 4, 4, 4, 4, 1, 0, 2, 2, 1, 1, 1, 2, 0, 2, 3, 5, 5,
         4, 4, 5, 3, 1, 2, 1, 3, 3, 2, 4, 6, 5, 3, 2, 3, 3, 2, 4, 3, 3,
         6, 6, 5, 3, 4, 4, 3, 4, 4, 4, 4, 6, 5, 5, 5, 5, 5, 5,
     }},
    {Power::GERMANY,
     {
         3, 3, 3, 4, 2, 4, 4, 3, 3, 4, 4, 2, 1, 1, 1, 3, 2, 4, 3, 3, 2,
         1, 1, 1, 0, 2, 3, 3, 3, 2, 2, 4, 4, 3, 3, 3, 4, 2, 0, 0, 2, 2,
         1, 3, 3, 5, 3, 4, 2, 1, 1, 1, 2, 4, 3, 4, 3, 4, 3, 2, 2, 2, 2,
         5, 4, 3, 3, 5, 3, 3, 5, 4, 3, 3, 5, 6, 6, 4, 4, 5, 4,
     }},
    {Power::ITALY,
     {
         6, 6, 5, 5, 5, 5, 5, 5, 4, 4, 4, 4, 4, 4, 4, 6, 5, 6, 4, 3, 4,
         3, 3, 4, 3, 5, 6, 6, 6, 3, 4, 3, 4, 3, 3, 3, 2, 2, 2, 3, 5, 5,
         4, 6, 5, 2, 2, 1, 1, 2, 3, 1, 4, 4, 4, 1, 1, 0, 0, 0, 3, 2, 1,
         4, 4, 3, 1, 2, 2, 1, 2, 2, 2, 2, 4, 3, 3, 3, 3, 3, 3,
     }},
    {Power::RUSSIA,
     {
         3, 3, 3, 4, 2, 4, 3, 2, 3, 4, 3, 3, 3, 3, 3, 1, 2, 1, 4, 4, 4,
         3, 3, 2, 3, 2, 1, 0, 0, 4, 4, 5, 5, 5, 5, 5, 5, 4, 2, 2, 1, 1,
         1, 0, 0, 5, 5, 5, 4, 2, 1, 3, 0, 0, 1, 4, 5, 5, 5, 4, 1, 2, 3,
         1, 1, 1, 4, 3, 3, 5, 3, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2,
     }},
    {Power::TURKEY,
     {
         7, 7, 7, 7, 6, 7, 7, 6, 6, 6, 6, 7, 6, 7, 7, 5, 6, 5, 6, 5, 7,
         6, 6, 5, 6, 6, 5, 4, 4, 6, 7, 4, 6, 5, 5, 5, 4, 5, 5, 5, 5, 4,
         5, 4, 3, 3, 4, 3, 5, 4, 4, 4, 4, 2, 3, 2, 4, 3, 4, 4, 3, 4, 3,
         1, 1, 2, 3, 1, 3, 3, 1, 2, 3, 2, 0, 0, 1, 1, 1, 0, 1,
     }}};

const std::map<Power, std::vector<int>> CIVIL_DISORDER_DISTS_FLEET{
    {Power::AUSTRIA,
     {
         8,  8,  7, 7,  7,  7,  7,  7,  6,  6,  6,  7, 8, 8,  8, 8,  8,
         8,  6,  5, 7,  -1, -1, 9,  9,  9,  10, -1, 9, 6, -1, 4, 6,  -1,
         6,  5,  4, 5,  -1, 10, 10, 10, 10, 11, -1, 3, 4, 3,  5, -1, -1,
         -1, -1, 6, -1, 2,  4,  3,  4,  1,  -1, 0,  0, 6, 5,  6, 1,  3,
         1,  2,  3, 2,  0,  -1, 5,  4,  4,  -1, 5,  4, 3,
     }},
    {Power::ENGLAND,
     {
         1,  0,  0, 0,  1,  1,  1, 1, 1, 1,  1,  2, 2, 2,  2, 2,  2,
         2,  2,  2, 2,  -1, -1, 3, 3, 3, 4,  -1, 3, 3, -1, 3, 3,  -1,
         3,  3,  3, 4,  -1, 4,  4, 4, 4, 5,  -1, 4, 4, 4,  5, -1, -1,
         -1, -1, 9, -1, 5,  5,  5, 5, 7, -1, -1, 7, 9, 8,  9, 6,  6,
         6,  6,  6, 6,  -1, -1, 8, 7, 7, -1, 8,  7, 7,
     }},
    {Power::FRANCE,
     {
         3,  3,  2, 3,  2,  2,  3, 3, 1, 2,  2,  2, 3, 3, 3, 3,  3,
         4,  0,  1, 1,  -1, -1, 4, 4, 4, 5,  -1, 4, 1, 0, 2, 2,  -1,
         2,  1,  2, 0,  -1, 5,  5, 5, 5, 6,  -1, 3, 1, 2, 1, -1, -1,
         -1, -1, 7, -1, 3,  2,  3, 3, 5, -1, -1, 5, 7, 6, 7, 4,  4,
         4,  4,  4, 4,  -1, -1, 6, 5, 5, -1, 6,  5, 5,
     }},
    {Power::GERMANY,
     {
         3,  3,  3,  5,  2,  4,  4,  3, 3, 4,  4,  2, 1,  1,  1,  3,  2,
         4,  4,  4,  3,  -1, -1, 1,  0, 2, 3,  -1, 4, 5,  -1, 5,  5,  -1,
         5,  5,  5,  6,  0,  0,  2,  2, 1, 3,  -1, 6, 6,  6,  7,  -1, -1,
         -1, -1, 11, -1, 7,  7,  7,  7, 9, -1, -1, 9, 11, 10, 11, 8,  8,
         8,  8,  8,  8,  -1, -1, 10, 9, 9, -1, 10, 9, 9,
     }},
    {Power::ITALY,
     {
         6,  6,  5, 5,  5,  5,  5, 5, 4, 4,  4,  5, 6, 6,  6, 6,  6,
         6,  4,  3, 5,  -1, -1, 7, 7, 7, 8,  -1, 7, 4, -1, 3, 4,  -1,
         4,  3,  2, 3,  -1, 8,  8, 8, 8, 9,  -1, 2, 2, 1,  2, -1, -1,
         -1, -1, 5, -1, 1,  1,  0, 0, 0, -1, -1, 1, 5, 4,  5, 1,  2,
         2,  1,  2, 2,  -1, -1, 4, 3, 3, -1, 4,  3, 3,
     }},
    {Power::RUSSIA,
     {
         3,  3, 3, 4,  2,  4,  3, 2, 3, 4,  3,  3, 3, 3,  3, 1,  2,
         1,  4, 4, 4,  -1, -1, 2, 3, 2, 1,  0,  0, 5, -1, 5, 5,  -1,
         5,  5, 5, 6,  -1, 3,  1, 1, 2, 0,  0,  5, 6, 5,  7, -1, -1,
         -1, 0, 0, -1, 4,  6,  5, 6, 6, -1, -1, 6, 1, 1,  1, 5,  3,
         5,  5, 4, 4,  -1, -1, 2, 3, 4, -1, 2,  2, 3,
     }},
    {Power::TURKEY,
     {
         8,  8,  7, 7,  7,  7,  7,  7,  6,  6,  6,  7, 8, 8,  8, 8,  8,
         8,  6,  5, 7,  -1, -1, 9,  9,  9,  10, -1, 9, 6, -1, 4, 6,  -1,
         6,  5,  4, 5,  -1, 10, 10, 10, 10, 11, -1, 3, 4, 3,  5, -1, -1,
         -1, -1, 2, -1, 2,  4,  3,  4,  4,  -1, -1, 4, 1, 1,  2, 3,  1,
         3,  3,  1, 2,  -1, -1, 0,  0,  1,  -1, 1,  0, 1,
     }},
};

// >>> ','.join(f"{{Loc::{loc}, {i} }}" for i, loc in enumerate(sorted(LOCS)))
std::map<Loc, int> LOC_ALPHA_IDX{
    {Loc::ADR, 0},     {Loc::AEG, 1},     {Loc::ALB, 2},     {Loc::ANK, 3},
    {Loc::APU, 4},     {Loc::ARM, 5},     {Loc::BAL, 6},     {Loc::BAR, 7},
    {Loc::BEL, 8},     {Loc::BER, 9},     {Loc::BLA, 10},    {Loc::BOH, 11},
    {Loc::BOT, 12},    {Loc::BRE, 13},    {Loc::BUD, 14},    {Loc::BUL, 15},
    {Loc::BUL_EC, 16}, {Loc::BUL_SC, 17}, {Loc::BUR, 18},    {Loc::CLY, 19},
    {Loc::CON, 20},    {Loc::DEN, 21},    {Loc::EAS, 22},    {Loc::EDI, 23},
    {Loc::ENG, 24},    {Loc::FIN, 25},    {Loc::GAL, 26},    {Loc::GAS, 27},
    {Loc::GRE, 28},    {Loc::HEL, 29},    {Loc::HOL, 30},    {Loc::ION, 31},
    {Loc::IRI, 32},    {Loc::KIE, 33},    {Loc::LON, 34},    {Loc::LVN, 35},
    {Loc::LVP, 36},    {Loc::LYO, 37},    {Loc::MAO, 38},    {Loc::MAR, 39},
    {Loc::MOS, 40},    {Loc::MUN, 41},    {Loc::NAF, 42},    {Loc::NAO, 43},
    {Loc::NAP, 44},    {Loc::NTH, 45},    {Loc::NWG, 46},    {Loc::NWY, 47},
    {Loc::PAR, 48},    {Loc::PIC, 49},    {Loc::PIE, 50},    {Loc::POR, 51},
    {Loc::PRU, 52},    {Loc::ROM, 53},    {Loc::RUH, 54},    {Loc::RUM, 55},
    {Loc::SER, 56},    {Loc::SEV, 57},    {Loc::SIL, 58},    {Loc::SKA, 59},
    {Loc::SMY, 60},    {Loc::SPA, 61},    {Loc::SPA_NC, 62}, {Loc::SPA_SC, 63},
    {Loc::STP, 64},    {Loc::STP_NC, 65}, {Loc::STP_SC, 66}, {Loc::SWE, 67},
    {Loc::SYR, 68},    {Loc::TRI, 69},    {Loc::TUN, 70},    {Loc::TUS, 71},
    {Loc::TYR, 72},    {Loc::TYS, 73},    {Loc::UKR, 74},    {Loc::VEN, 75},
    {Loc::VIE, 76},    {Loc::WAL, 77},    {Loc::WAR, 78},    {Loc::WES, 79},
    {Loc::YOR, 80}};

} // namespace dipcc
