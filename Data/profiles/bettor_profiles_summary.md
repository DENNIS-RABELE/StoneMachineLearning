# Bettor-Level Profiles

Input file: `Data\cleaned\cleaned_bets.csv`
Profile rows: `8,000`
Output file: `Data\profiles\bettor_profiles.csv`

## What This Dataset Is For

Each row summarizes one bettor. These features are ready for admin analytics and later ML clustering.

## Core Feature Groups

- Timing: favorite time band, favorite hour, favorite day, weekend rate, night rate
- Strategy: preferred strategy style, option family, combo rate, preferred option code
- Value: total stake, average stake, payout, profit, ROI
- Odds behavior: average odds, preferred odds band, high odds rate
- Outcome behavior: win rate and loss rate
- Promotion support: promotion targeting signal
- Safety support: responsible gambling risk hint

## Promotion Signals

         promotion_targeting_signal  bettor_count
                    High Odds Boost          7877
         General Personalized Offer            92
Accumulator Insurance / Combo Boost            28
             Retention / Safer Play             2
                Night-Time Campaign             1

## Preferred Strategy Styles

preferred_strategy_style  bettor_count
        High-Odds Hunter          6148
     Combo / Multi-Phase          1852

## Favorite Time Bands

favorite_time_band  bettor_count
          Midnight          2429
           Morning          2358
             Lunch          2323
         Afternoon           471
           Evening           236
             Night           183

## Responsible Gambling Risk Hints

responsible_gambling_risk_hint  bettor_count
                        Medium          7118
                           Low           797
                          High            85
