# Live vs paper v4b, same signals

Written 19 Nov 2026 00:28 IST. Live = real orders (`data/trader/live` and `live_archive`); paper = paper_v4b's fill on the same market within 15 s; estimate = the live estimate's predicted fill for that paper trade. Live P&L uses the venue's sizing (5 x limit spent, extra shares on price improvement). Signals while live was paused are listed, not counted.

## Summary (live active only)

| | |
|---|---|
| Live orders | 287 (151 filled) |
| Paper filled the same market | 251 |
| **Lost the race where paper filled** | **84 of 251** |
| **Refused by Polymarket (not a race)** | **32** (25 where paper filled) |
| **Live price minus paper price** (both filled) | **+0.040** per share (n 142) |
| Live price minus live-estimate price | +0.024 (n 139) |
| Live settled P&L | +9.10 USD on 453.29 spent (+2.0%), 141 bets |
| Paper v4b on those markets | +100.18 USD on 618.01 (+16.2%) |
| Orders while live was paused (not counted) | 0 |

## Every live order

| Time (IST) | Signal | Limit | Live fill | Paper fill | Estimate | Live result | Live P&L | Paper P&L |
|---|---|---|---|---|---|---|---|---|
| 18 Nov 20:52:29 | BTC up +6.3bp 5m | 0.38 | 0.370 | 0.31 | 0.340 | open |  | -1.62 |
| 18 Nov 20:46:32 | BTC down -6.2bp 5m | 0.46 | 0.360 | 0.36 | 0.360 | lost | -3.02 | -1.88 |
| 18 Nov 20:46:32 | BTC down -6.2bp 15m | 0.53 | 0.440 | 0.43 | 0.434 | open |  | +2.76 |
| 18 Nov 20:40:07 | BTC down -6.0bp 5m | 0.60 | 0.540 | 0.50 | 0.549 | lost | -3.43 | -2.59 |
| 18 Nov 20:36:04 | BTC up +6.2bp 5m | 0.33 | 0.310 | 0.24 | 0.300 | lost | -1.84 | -1.26 |
| 18 Nov 20:30:09 | BTC down -6.4bp 5m | 0.50 | 0.430 | 0.41 | 0.410 | lost | -3.01 | -2.13 |
| 18 Nov 20:30:09 | BTC down -6.4bp 15m | 0.55 | 0.460 | 0.46 | 0.460 | lost | -3.39 | -2.39 |
| 18 Nov 20:20:09 | BTC down -6.3bp 5m | 0.35 | 0.320 | 0.25 | 0.278 | lost | -2.00 | -1.32 |
| 18 Nov 20:16:31 | BTC up +6.3bp 15m | 0.51 | 0.410 | 0.41 | 0.410 | WON | +4.46 | +2.87 |
| 18 Nov 20:16:31 | BTC up +6.3bp 5m | 0.41 | 0.320 | 0.32 | 0.320 | WON | +5.48 | +3.32 |
| 18 Nov 20:10:31 | BTC down -6.1bp 5m | 0.76 | 0.680 | 0.66 | 0.660 | WON | +1.91 | +1.62 |
| 18 Nov 20:02:32 | BTC up +6.4bp 5m | 0.31 | 0.290 |  |  | lost | -1.73 |  |
| 18 Nov 20:01:16 | BTC down -6.0bp 5m | 0.63 |  | 0.52 | 0.530 | missed |  | +2.31 |
| 18 Nov 20:01:16 | BTC down -6.0bp 15m | 0.59 | 0.550 | 0.54 | 0.550 | WON | +2.50 | +2.21 |
| 18 Nov 17:34:20 | BTC down -6.0bp 15m | 0.81 | 0.750 | 0.71 | 0.741 | lost | -4.44 | -3.62 |
| 18 Nov 16:42:44 | BTC up +6.3bp 5m | 0.34 |  | 0.24 | 0.261 | missed |  | +3.74 |
| 18 Nov 16:26:53 | BTC down -6.1bp 5m | 0.34 |  | 0.31 |  | missed |  | +3.38 |
| 18 Nov 16:26:53 | BTC down -6.1bp 15m | 0.14 |  | 0.04 |  | missed |  | -0.21 |
| 18 Nov 13:26:04 | BTC up +6.6bp 5m | 0.63 |  | 0.53 |  | missed |  | +2.26 |
| 18 Nov 12:26:06 | BTC up +6.3bp 5m | 0.82 |  | 0.72 |  | missed |  | +1.33 |
| 18 Nov 12:26:06 | BTC up +6.3bp 15m | 0.70 |  | 0.60 | 0.680 | missed |  | -3.08 |
| 18 Nov 00:47:07 | BTC up +6.0bp 15m | 0.56 | 0.520 | 0.46 | 0.480 | open |  | -2.39 |
| 18 Nov 00:47:07 | BTC up +6.0bp 5m | 0.52 |  | 0.42 |  | missed |  | -2.19 |
| 18 Nov 00:25:07 | BTC down -6.0bp 5m | 0.85 |  | 0.82 |  | missed |  | +0.85 |
| 18 Nov 00:25:07 | BTC down -6.0bp 15m | 0.23 |  |  |  | missed |  |  |
| 18 Nov 00:21:53 | BTC up +6.0bp 15m | 0.61 |  | 0.54 |  | missed |  | +2.21 |
| 17 Nov 23:49:46 | BTC up +6.3bp 15m | 0.85 | 0.830 | 0.77 | 0.810 | WON | +0.82 | +1.09 |
| 17 Nov 23:16:37 | BTC up +6.1bp 5m | 0.75 | 0.750 | 0.72 | 0.720 | WON | +1.18 | +1.33 |
| 17 Nov 23:16:37 | BTC up +6.1bp 15m | 0.70 | 0.630 | 0.63 | 0.630 | WON | +1.97 | +1.77 |
| 17 Nov 23:06:36 | BTC up +6.1bp 5m | 0.64 |  | 0.58 | 0.587 | missed |  | -2.99 |
| 17 Nov 23:06:36 | BTC up +6.1bp 15m | 0.35 | 0.340 | 0.32 | 0.340 | lost | -1.83 | -1.68 |
| 17 Nov 22:55:13 | BTC up +6.2bp 5m | 0.53 |  | 0.43 | 0.497 | missed |  | -2.24 |
| 17 Nov 22:49:27 | BTC up +6.3bp 15m | 0.85 | 0.810 | 0.81 | 0.810 | lost | -4.30 | -4.10 |
| 17 Nov 22:40:37 | BTC up +6.1bp 5m | 0.69 | 0.640 | 0.58 | 0.580 | lost | -3.53 | -2.99 |
| 17 Nov 22:35:12 | BTC up +6.0bp 5m | 0.83 | 0.780 | 0.74 | 0.750 | WON | +1.11 | +1.23 |
| 17 Nov 22:30:38 | BTC up +6.6bp 15m | 0.41 | 0.340 | 0.31 | 0.340 | WON | +3.90 | +3.38 |
| 17 Nov 22:30:38 | BTC up +6.6bp 5m | 0.29 | 0.250 | 0.19 | 0.240 | lost | -1.52 | -1.00 |
| 17 Nov 22:26:34 | BTC down -6.1bp 5m | 0.83 | 0.760 | 0.73 | 0.730 | lost | -4.21 | -3.72 |
| 17 Nov 22:15:41 | BTC down -6.1bp 15m | 0.65 | 0.600 | 0.58 | 0.600 | WON | +2.08 | +2.01 |
| 17 Nov 22:15:41 | BTC down -6.1bp 5m | 0.71 | 0.700 | 0.65 | 0.650 | WON | +1.45 | +1.67 |
| 17 Nov 22:10:53 | BTC up +6.2bp 5m | 0.30 | 0.280 | 0.20 | 0.200 | lost | -1.57 | -1.06 |
| 17 Nov 22:06:09 | BTC down -6.0bp 5m | 0.85 |  | 0.82 | 0.840 | missed |  | +0.85 |
| 17 Nov 22:02:44 | BTC down -6.2bp 15m | 0.60 | 0.560 | 0.51 | 0.545 | WON | +2.27 | +2.36 |
| 17 Nov 22:02:44 | BTC down -6.2bp 5m | 0.61 | 0.560 | 0.54 | 0.610 | WON | +2.31 | +2.21 |
| 17 Nov 21:55:24 | BTC down -6.8bp 5m | 0.65 | 0.580 | 0.55 | 0.550 | WON | +2.27 | +2.16 |
| 17 Nov 21:51:10 | BTC up +6.6bp 5m | 0.45 | 0.420 | 0.34 | 0.394 | lost | -2.34 | -1.78 |
| 17 Nov 21:45:04 | BTC up +6.0bp 15m | 0.63 | 0.540 | 0.53 | 0.538 | lost | -3.24 | -1.70 |
| 17 Nov 21:45:04 | BTC up +6.0bp 5m | 0.61 | 0.560 | 0.56 | 0.560 | lost | -3.14 | -2.89 |
| 17 Nov 21:43:47 | BTC up +6.9bp 5m | 0.11 |  | 0.01 | 0.008 | refused: other leg under $1 |  | -0.03 |
| 17 Nov 21:35:29 | BTC down -6.0bp 5m | 0.51 | 0.430 | 0.43 | 0.430 | lost | -2.64 | -2.24 |
| 17 Nov 21:31:00 | BTC up +6.5bp 5m | 0.59 | 0.550 | 0.50 | 0.500 | WON | +2.33 | +2.41 |
| 17 Nov 21:31:00 | BTC up +6.5bp 15m | 0.63 | 0.540 | 0.54 | 0.540 | WON | +2.60 | +2.21 |
| 17 Nov 21:25:11 | BTC up +6.3bp 5m | 0.58 | 0.490 | 0.51 | 0.510 | WON | +2.93 | +2.36 |
| 17 Nov 21:20:48 | BTC down -6.2bp 5m | 0.65 | 0.620 | 0.57 | 0.613 | WON | +1.91 | +2.06 |
| 17 Nov 21:15:26 | BTC down -6.5bp 5m | 0.69 | 0.650 | 0.59 | 0.590 | WON | +1.78 | +1.97 |
| 17 Nov 21:15:26 | BTC down -6.5bp 15m | 0.65 | 0.560 | 0.58 | 0.580 | WON | +2.47 | +2.01 |
| 17 Nov 21:13:26 | BTC up +6.7bp 5m | 0.10 |  | 0.00 | 0.001 | refused: other leg under $1 |  | -0.01 |
| 17 Nov 21:13:26 | BTC up +6.7bp 15m | 0.10 |  | 0.00 |  | refused: other leg under $1 |  | -0.01 |
| 17 Nov 20:52:52 | BTC down -6.3bp 5m | 0.11 |  | 0.01 | 0.009 | refused: other leg under $1 |  | -0.05 |
| 17 Nov 20:52:52 | BTC down -6.3bp 15m | 0.15 |  | 0.06 | 0.060 | refused: other leg under $1 |  | -0.32 |
| 17 Nov 20:35:32 | BTC down -7.7bp 5m | 0.73 |  |  |  | missed |  |  |
| 17 Nov 20:30:11 | BTC up +6.1bp 5m | 0.60 | 0.600 | 0.50 | 0.514 | lost | -3.08 | -2.59 |
| 17 Nov 20:30:11 | BTC up +6.1bp 15m | 0.61 | 0.550 | 0.51 | 0.530 | lost | -3.14 | -2.64 |
| 17 Nov 20:27:41 | BTC up +6.2bp 5m | 0.70 |  | 0.60 | 0.619 | missed |  | +1.92 |
| 17 Nov 20:27:41 | BTC up +6.2bp 15m | 0.11 |  |  |  | refused: other leg under $1 |  |  |
| 17 Nov 19:39:26 | BTC up +6.3bp 15m | 0.12 |  | 0.02 | 0.049 | refused: other leg under $1 |  | -0.11 |
| 17 Nov 19:16:07 | BTC up +6.1bp 5m | 0.40 |  | 0.30 | 0.300 | missed |  | -1.57 |
| 17 Nov 19:16:07 | BTC up +6.1bp 15m | 0.52 | 0.460 | 0.42 | 0.430 | WON | +2.97 | +2.81 |
| 17 Nov 18:26:39 | BTC up +6.1bp 5m | 0.61 |  | 0.51 |  | missed |  | +2.36 |
| 17 Nov 18:26:39 | BTC up +6.1bp 15m | 0.60 |  | 0.50 |  | missed |  | +2.41 |
| 17 Nov 17:01:36 | BTC up +6.2bp 15m | 0.85 | 0.810 | 0.78 | 0.822 | WON | +0.94 | +1.04 |
| 17 Nov 16:48:18 | BTC up +6.1bp 15m | 0.84 | 0.800 | 0.74 | 0.830 | WON | +0.99 | +1.23 |
| 17 Nov 16:41:07 | BTC up +6.2bp 5m | 0.85 | 0.850 | 0.78 | 0.786 | WON | +0.30 | +1.04 |
| 17 Nov 16:31:57 | BTC down -6.3bp 5m | 0.16 | 0.160 |  |  | lost | -1.06 |  |
| 17 Nov 16:30:26 | BTC up +6.0bp 15m | 0.74 | 0.680 | 0.65 | 0.654 | WON | +1.67 | +0.96 |
| 17 Nov 16:30:26 | BTC up +6.0bp 5m | 0.62 |  | 0.53 | 0.530 | missed |  | +2.26 |
| 17 Nov 16:21:45 | BTC down -6.0bp 5m | 0.80 |  | 0.72 |  | missed |  | +1.33 |
| 17 Nov 16:21:45 | BTC down -6.0bp 15m | 0.75 |  | 0.67 |  | missed |  | +1.57 |
| 17 Nov 15:53:37 | BTC down -6.1bp 15m | 0.76 |  |  |  | missed |  |  |
| 17 Nov 15:49:24 | BTC down -6.1bp 15m | 0.41 |  | 0.36 | 0.364 | missed |  | +3.12 |
| 17 Nov 15:43:15 | BTC down -6.4bp 5m | 0.24 |  | 0.14 |  | missed |  | -0.74 |
| 17 Nov 15:37:19 | BTC down -6.1bp 5m | 0.85 |  | 0.85 |  | missed |  | +0.71 |
| 17 Nov 15:37:19 | BTC down -6.1bp 15m | 0.62 | 0.590 | 0.53 | 0.618 | WON | +2.07 | +2.26 |
| 17 Nov 15:17:12 | BTC down -6.2bp 5m | 0.79 |  | 0.69 | 0.700 | missed |  | +1.48 |
| 17 Nov 15:17:12 | BTC down -6.2bp 15m | 0.66 | 0.640 | 0.59 |  | WON | +1.78 | +1.97 |
| 17 Nov 14:30:21 | BTC down -6.7bp 5m | 0.43 |  | 0.31 | 0.410 | missed |  | +3.38 |
| 17 Nov 14:30:21 | BTC down -6.7bp 15m | 0.53 | 0.490 | 0.43 | 0.464 | open |  | +2.76 |
| 17 Nov 13:57:59 | BTC down -6.4bp 5m | 0.57 |  |  |  | missed |  |  |
| 17 Nov 13:57:59 | BTC down -6.4bp 15m | 0.85 |  |  |  | missed |  |  |
| 17 Nov 13:32:16 | BTC down -6.5bp 5m | 0.85 |  | 0.84 |  | missed |  | +0.75 |
| 17 Nov 13:32:16 | BTC down -6.5bp 15m | 0.76 |  | 0.68 |  | missed |  | +1.52 |
| 17 Nov 13:08:55 | BTC up +6.3bp 5m | 0.38 |  | 0.28 |  | missed |  | +3.53 |
| 17 Nov 13:08:55 | BTC up +6.3bp 15m | 0.24 |  | 0.14 | 0.190 | missed |  | -0.74 |
| 17 Nov 01:47:53 | BTC down -6.0bp 15m | 0.45 |  | 0.35 | 0.433 | missed |  | -1.83 |
| 17 Nov 01:47:53 | BTC down -6.0bp 5m | 0.46 |  | 0.36 | 0.454 | missed |  | -1.88 |
| 17 Nov 01:35:05 | BTC down -6.1bp 5m | 0.68 | 0.640 | 0.58 | 0.580 | lost | -3.48 | -2.99 |
| 17 Nov 01:35:05 | BTC down -6.1bp 15m | 0.55 | 0.530 | 0.49 | 0.507 | WON | +2.35 | +2.46 |
| 17 Nov 01:11:48 | BTC down -6.0bp 5m | 0.81 |  | 0.71 | 0.790 | missed |  | -3.62 |
| 17 Nov 00:48:43 | BTC up +6.3bp 15m | 0.59 |  | 0.57 |  | missed |  | +2.06 |
| 17 Nov 00:48:43 | BTC up +6.3bp 5m | 0.68 |  | 0.58 |  | missed |  | +2.01 |
| 17 Nov 00:41:31 | BTC up +6.2bp 5m | 0.31 |  | 0.21 |  | missed |  | -1.11 |
| 17 Nov 00:41:31 | BTC up +6.2bp 15m | 0.14 |  |  |  | refused: other leg under $1 |  |  |
| 17 Nov 00:38:42 | BTC up +6.3bp 5m | 0.15 |  | 0.05 | 0.117 | refused: other leg under $1 |  | -0.27 |
| 17 Nov 00:38:42 | BTC up +6.3bp 15m | 0.18 |  | 0.08 | 0.160 | refused: other leg under $1 |  | -0.43 |
| 17 Nov 00:19:09 | BTC up +6.2bp 15m | 0.75 | 0.730 | 0.65 | 0.710 | WON | +1.32 | +1.67 |
| 17 Nov 00:13:19 | BTC down -6.1bp 5m | 0.11 |  | 0.01 | 0.010 | refused: other leg under $1 |  | -0.05 |
| 17 Nov 00:13:19 | BTC down -6.1bp 15m | 0.11 |  | 0.01 |  | refused: other leg under $1 |  | -0.05 |
| 16 Nov 23:51:47 | BTC up +6.2bp 5m | 0.50 |  | 0.46 |  | missed |  | -2.39 |
| 16 Nov 23:51:47 | BTC up +6.2bp 15m | 0.59 |  | 0.50 |  | missed |  | -2.59 |
| 16 Nov 23:36:32 | BTC up +6.0bp 15m | 0.75 | 0.750 | 0.71 | 0.717 | WON | +1.18 | +1.38 |
| 16 Nov 22:45:20 | BTC up +6.1bp 15m | 0.80 | 0.750 | 0.74 | 0.750 | WON | +1.27 | +1.23 |
| 16 Nov 21:20:53 | BTC up +6.0bp 5m | 0.84 | 0.840 | 0.75 | 0.760 | lost | -4.25 | -3.82 |
| 16 Nov 21:15:12 | BTC up +6.4bp 5m | 0.85 | 0.760 | 0.76 | 0.780 | WON | +1.28 | +1.14 |
| 16 Nov 21:15:12 | BTC up +6.4bp 15m | 0.74 | 0.650 | 0.64 | 0.656 | WON | +1.91 | +1.72 |
| 16 Nov 21:13:30 | BTC down -6.5bp 5m | 0.11 |  | 0.01 | 0.010 | refused: other leg under $1 |  | -0.05 |
| 16 Nov 21:00:30 | BTC up +6.1bp 15m | 0.65 | 0.570 | 0.56 | 0.570 | WON | +2.37 | +0.33 |
| 16 Nov 21:00:30 | BTC up +6.1bp 5m | 0.69 | 0.660 | 0.60 | 0.650 | lost | -3.53 | -3.08 |
| 16 Nov 20:56:52 | BTC up +6.1bp 5m | 0.41 | 0.370 | 0.34 | 0.340 | WON | +3.41 | +3.22 |
| 16 Nov 20:51:26 | BTC up +6.4bp 5m | 0.35 | 0.330 | 0.28 | 0.290 | lost | -1.83 | -1.47 |
| 16 Nov 20:45:14 | BTC down -6.0bp 15m | 0.67 | 0.580 | 0.57 | 0.570 | WON | +2.34 | +2.06 |
| 16 Nov 20:45:14 | BTC down -6.0bp 5m | 0.74 | 0.610 | 0.64 | 0.640 | WON | +2.28 | +1.72 |
| 16 Nov 20:41:36 | BTC up +6.1bp 5m | 0.38 | 0.370 | 0.27 | 0.270 | lost | -1.98 | -1.42 |
| 16 Nov 20:37:47 | BTC up +6.7bp 5m | 0.20 | 0.110 | 0.12 | 0.120 | lost | -1.03 | -0.64 |
| 16 Nov 20:31:57 | BTC down -6.2bp 15m | 0.85 | 0.820 | 0.80 | 0.810 | WON | +0.88 | +0.94 |
| 16 Nov 20:25:51 | BTC up +6.6bp 5m | 0.71 | 0.700 | 0.61 | 0.630 | lost | -3.62 | -3.13 |
| 16 Nov 20:22:56 | BTC up +6.4bp 5m | 0.72 |  | 0.62 | 0.620 | missed |  | +1.82 |
| 16 Nov 20:15:11 | BTC down -6.1bp 15m | 0.68 | 0.590 | 0.59 | 0.590 | WON | +2.28 | +1.97 |
| 16 Nov 20:15:11 | BTC down -6.1bp 5m | 0.74 | 0.650 | 0.64 | 0.640 | WON | +1.91 | +1.72 |
| 16 Nov 20:13:12 | BTC down -6.8bp 5m | 0.85 |  |  |  | missed |  |  |
| 16 Nov 20:10:40 | BTC down -6.3bp 5m | 0.85 |  |  |  | missed |  |  |
| 16 Nov 20:05:54 | BTC up +6.2bp 5m | 0.74 | 0.720 | 0.71 | 0.710 | WON | +1.37 | +1.38 |
| 16 Nov 20:00:33 | BTC down -6.0bp 5m | 0.50 | 0.490 | 0.42 | 0.420 | lost | -2.59 | -2.19 |
| 16 Nov 20:00:33 | BTC down -6.0bp 15m | 0.57 | 0.500 | 0.49 | 0.530 | lost | -2.94 | -2.54 |
| 16 Nov 19:50:03 | BTC up +6.1bp 5m | 0.51 |  | 0.51 | 0.510 | missed |  | -2.64 |
| 16 Nov 19:45:39 | BTC up +6.1bp 15m | 0.59 | 0.560 | 0.51 | 0.529 | WON | +2.23 | +2.36 |
| 16 Nov 19:45:39 | BTC up +6.1bp 5m | 0.58 |  | 0.52 | 0.559 | missed |  | +1.20 |
| 16 Nov 19:42:00 | BTC down -6.4bp 5m | 0.12 |  | 0.03 | 0.030 | refused: other leg under $1 |  | -0.16 |
| 16 Nov 19:30:42 | BTC down -6.2bp 15m | 0.67 | 0.580 | 0.58 | 0.580 | lost | -3.44 | -2.99 |
| 16 Nov 19:30:42 | BTC down -6.2bp 5m | 0.66 | 0.620 | 0.58 | 0.580 | WON | +1.94 | +2.01 |
| 16 Nov 19:00:20 | BTC down -6.7bp 15m | 0.42 | 0.380 | 0.31 | 0.310 | lost | -2.18 | -1.62 |
| 16 Nov 19:00:20 | BTC down -6.7bp 5m | 0.31 | 0.300 | 0.21 | 0.210 | lost | -1.62 | -1.11 |
| 16 Nov 18:58:22 | BTC down -6.4bp 5m | 0.25 |  |  |  | missed |  |  |
| 16 Nov 18:58:22 | BTC down -6.4bp 15m | 0.34 |  |  |  | missed |  |  |
| 16 Nov 18:55:37 | BTC up +6.4bp 5m | 0.66 |  | 0.56 |  | missed |  | +2.11 |
| 16 Nov 18:55:37 | BTC up +6.4bp 15m | 0.63 |  | 0.53 |  | missed |  | +2.26 |
| 16 Nov 18:40:31 | BTC up +6.1bp 5m | 0.25 |  | 0.15 | 0.211 | missed |  | -0.79 |
| 16 Nov 18:40:31 | BTC up +6.1bp 15m | 0.57 |  | 0.47 | 0.569 | missed |  | -2.44 |
| 16 Nov 18:21:06 | BTC down -6.7bp 5m | 0.85 | 0.850 | 0.77 | 0.828 | WON | +0.71 | +1.09 |
| 16 Nov 18:19:56 | BTC down -6.2bp 15m | 0.78 | 0.760 | 0.71 | 0.734 | WON | +1.17 | +1.38 |
| 16 Nov 17:42:21 | BTC up +6.1bp 15m | 0.10 |  | 0.00 |  | refused: other leg under $1 |  | -0.01 |
| 16 Nov 17:40:54 | BTC down -6.3bp 5m | 0.85 | 0.820 | 0.79 | 0.790 | WON | +0.88 | +0.99 |
| 16 Nov 16:47:08 | BTC up +6.5bp 15m | 0.85 | 0.850 | 0.83 | 0.840 | open |  | +0.03 |
| 16 Nov 16:42:14 | BTC down -6.1bp 5m | 0.81 |  | 0.78 | 0.780 | missed |  | +1.04 |
| 16 Nov 16:42:14 | BTC down -6.1bp 15m | 0.17 |  | 0.10 | 0.100 | refused: other leg under $1 |  | -0.53 |
| 16 Nov 15:38:32 | BTC down -6.3bp 5m | 0.22 |  | 0.12 | 0.170 | missed |  | -0.64 |
| 16 Nov 15:38:32 | BTC down -6.3bp 15m | 0.40 |  | 0.30 |  | missed |  | -1.57 |
| 16 Nov 15:23:13 | BTC up +6.1bp 5m | 0.18 |  | 0.07 | 0.121 | refused: other leg under $1 |  | -0.37 |
| 16 Nov 15:23:13 | BTC up +6.1bp 15m | 0.20 | 0.180 | 0.10 | 0.100 | lost | -1.05 | -0.53 |
| 16 Nov 15:01:45 | BTC up +6.1bp 5m | 0.85 |  | 0.83 |  | missed |  | +0.80 |
| 16 Nov 15:01:45 | BTC up +6.1bp 15m | 0.76 | 0.750 | 0.74 | 0.740 | WON | +1.20 | +1.23 |
| 16 Nov 14:53:09 | BTC up +6.1bp 15m | 0.85 |  |  |  | missed |  |  |
| 16 Nov 14:36:03 | BTC down -6.2bp 5m | 0.69 | 0.680 | 0.68 | 0.680 | WON | +1.55 | +1.52 |
| 16 Nov 14:33:51 | BTC up +6.1bp 5m | 0.11 |  |  |  | refused: other leg under $1 |  |  |
| 16 Nov 14:31:21 | BTC down -6.2bp 15m | 0.80 | 0.730 | 0.72 | 0.720 | WON | +1.41 | +1.33 |
| 16 Nov 14:31:21 | BTC down -6.2bp 5m | 0.85 |  | 0.84 | 0.840 | missed |  | +0.75 |
| 16 Nov 13:49:58 | BTC down -6.5bp 15m | 0.85 |  |  |  | missed |  |  |
| 16 Nov 13:12:24 | BTC down -6.4bp 5m | 0.27 |  | 0.17 |  | missed |  | -0.90 |
| 16 Nov 13:12:24 | BTC down -6.4bp 15m | 0.10 |  | 0.00 | 0.001 | refused: other leg under $1 |  | -0.01 |
| 16 Nov 13:06:24 | BTC up +6.1bp 5m | 0.39 |  | 0.29 |  | missed |  | -1.52 |
| 16 Nov 12:55:44 | BTC up +6.3bp 5m | 0.77 |  | 0.65 | 0.770 | missed |  | +1.67 |
| 16 Nov 12:51:19 | BTC up +6.3bp 5m | 0.75 |  | 0.62 | 0.620 | missed |  | +1.82 |
| 16 Nov 12:51:19 | BTC up +6.3bp 15m | 0.51 |  | 0.38 | 0.380 | missed |  | +3.02 |
| 16 Nov 12:02:38 | BTC up +6.6bp 15m | 0.85 | 0.820 | 0.74 | 0.740 | WON | +0.88 | +1.23 |
| 16 Nov 01:13:13 | BTC up +6.7bp 5m | 0.56 |  | 0.46 |  | missed |  | +2.61 |
| 16 Nov 01:13:13 | BTC up +6.7bp 15m | 0.35 |  | 0.25 | 0.320 | missed |  | +3.68 |
| 16 Nov 00:50:11 | BTC up +6.2bp 15m | 0.31 | 0.300 | 0.26 | 0.260 | lost | -1.62 | -1.37 |
| 16 Nov 00:50:11 | BTC up +6.2bp 5m | 0.68 |  | 0.58 | 0.580 | missed |  | +2.01 |
| 16 Nov 00:40:10 | BTC up +6.1bp 5m | 0.85 |  |  |  | missed |  |  |
| 16 Nov 00:39:04 | BTC up +6.1bp 15m | 0.85 |  |  |  | missed |  |  |
| 15 Nov 23:58:26 | BTC down -6.1bp 15m | 0.11 |  |  |  | refused: under $1 |  |  |
| 15 Nov 23:45:40 | BTC up +6.4bp 5m | 0.84 | 0.800 | 0.74 | 0.740 | WON | +0.99 | +1.23 |
| 15 Nov 23:45:40 | BTC up +6.4bp 15m | 0.71 |  | 0.61 | 0.628 | missed |  | -3.13 |
| 15 Nov 22:49:02 | BTC up +7.0bp 15m | 0.83 | 0.820 | 0.73 | 0.794 | open |  | +1.28 |
| 15 Nov 22:26:45 | BTC up +6.5bp 15m | 0.31 |  | 0.22 |  | missed |  | +3.84 |
| 15 Nov 22:05:14 | BTC down -6.5bp 5m | 0.53 | 0.490 | 0.43 | 0.490 | WON | +2.67 | +2.76 |
| 15 Nov 22:03:36 | BTC down -6.1bp 15m | 0.60 | 0.540 |  |  | lost | -3.09 |  |
| 15 Nov 22:03:36 | BTC down -6.1bp 5m | 0.63 | 0.590 |  |  | WON | +2.10 |  |
| 15 Nov 22:00:53 | BTC down -6.2bp 15m | 0.22 |  | 0.13 | 0.161 | refused: other leg under $1 |  | -0.69 |
| 15 Nov 22:00:53 | BTC down -6.2bp 5m | 0.15 |  | 0.05 | 0.050 | refused: under $1 |  | +4.73 |
| 15 Nov 21:58:43 | BTC up +6.2bp 15m | 0.11 |  |  |  | refused: under $1 |  |  |
| 15 Nov 21:54:17 | BTC up +6.0bp 15m | 0.14 |  | 0.04 | 0.090 | refused: under $1 |  | -0.21 |
| 15 Nov 21:53:03 | BTC down -6.1bp 5m | 0.85 |  | 0.76 |  | missed |  | +1.14 |
| 15 Nov 21:19:20 | BTC up +6.1bp 15m | 0.76 | 0.760 |  |  | WON | +1.14 |  |
| 15 Nov 21:15:35 | BTC down -6.3bp 5m | 0.52 |  | 0.42 | 0.420 | missed |  | -2.19 |
| 15 Nov 21:15:35 | BTC down -6.3bp 15m | 0.55 |  | 0.45 |  | missed |  | -2.34 |
| 15 Nov 21:12:13 | BTC down -6.3bp 5m | 0.56 |  | 0.46 |  | missed |  | +2.61 |
| 15 Nov 21:06:53 | BTC down -6.9bp 5m | 0.37 |  | 0.27 |  | missed |  | -1.42 |
| 15 Nov 21:06:53 | BTC down -6.9bp 15m | 0.29 | 0.290 | 0.19 | 0.268 | lost | -1.52 | -1.00 |
| 15 Nov 20:53:44 | BTC down -6.4bp 15m | 0.59 |  | 0.49 | 0.520 | missed |  | +2.46 |
| 15 Nov 20:40:08 | BTC up +6.1bp 5m | 0.85 | 0.810 | 0.79 | 0.790 | WON | +0.94 | +0.99 |
| 15 Nov 20:36:22 | BTC down -6.0bp 5m | 0.67 | 0.670 | 0.59 | 0.594 | lost | -3.43 | -1.71 |
| 15 Nov 20:33:15 | BTC down -6.0bp 15m | 0.75 | 0.710 | 0.65 | 0.700 | WON | +1.46 | +1.67 |
| 15 Nov 20:10:42 | BTC down -6.0bp 5m | 0.85 | 0.780 | 0.74 | 0.780 | WON | +1.14 | +1.23 |
| 15 Nov 20:08:07 | BTC down -6.3bp 5m | 0.52 |  |  |  | missed |  |  |
| 15 Nov 20:05:45 | BTC down -6.2bp 5m | 0.56 |  | 0.46 | 0.460 | missed |  | +2.61 |
| 15 Nov 20:03:47 | BTC up +6.1bp 5m | 0.63 |  |  |  | missed |  |  |
| 15 Nov 20:02:35 | BTC down -6.2bp 5m | 0.57 |  |  |  | missed |  |  |
| 15 Nov 20:01:01 | BTC down -6.2bp 5m | 0.70 |  | 0.63 | 0.700 | missed |  | -3.23 |
| 15 Nov 20:01:01 | BTC down -6.2bp 15m | 0.65 | 0.620 | 0.55 | 0.581 | WON | +1.91 | +2.16 |
| 15 Nov 19:51:15 | BTC down -6.2bp 5m | 0.85 | 0.840 | 0.75 | 0.790 | WON | +0.76 | +1.18 |
| 15 Nov 19:51:15 | BTC down -6.2bp 15m | 0.52 |  |  |  | missed |  |  |
| 15 Nov 19:48:42 | BTC up +6.8bp 15m | 0.85 |  | 0.85 | 0.850 | missed |  | -4.29 |
| 15 Nov 19:35:17 | BTC down -6.0bp 5m | 0.80 | 0.750 | 0.74 | 0.740 | WON | +1.27 | +1.23 |
| 15 Nov 19:22:16 | BTC down -7.4bp 5m | 0.53 |  | 0.40 | 0.420 | missed |  | +2.92 |
| 15 Nov 19:22:16 | BTC down -7.4bp 15m | 0.51 | 0.490 | 0.41 | 0.420 | WON | +2.57 | +2.87 |
| 15 Nov 19:07:46 | BTC down -6.1bp 5m | 0.17 |  | 0.07 | 0.150 | refused: under $1 |  | +4.63 |
| 15 Nov 19:07:46 | BTC down -6.1bp 15m | 0.60 |  | 0.50 | 0.582 | refused: other leg under $1 |  | +2.41 |
| 15 Nov 18:58:09 | BTC down -6.3bp 5m | 0.30 |  | 0.20 |  | missed |  | +3.94 |
| 15 Nov 18:48:42 | BTC up +6.1bp 15m | 0.80 | 0.730 | 0.70 | 0.700 | WON | +1.41 | +1.43 |
| 15 Nov 18:31:24 | BTC up +6.2bp 15m | 0.73 | 0.690 | 0.63 | 0.689 | WON | +1.56 | +1.77 |
| 15 Nov 18:31:24 | BTC up +6.2bp 5m | 0.85 | 0.850 | 0.75 | 0.823 | WON | +0.71 | +1.18 |
| 15 Nov 18:27:23 | BTC up +6.0bp 5m | 0.85 |  | 0.82 | 0.820 | missed |  | +0.85 |
| 15 Nov 18:19:01 | BTC down -6.6bp 15m | 0.71 | 0.610 | 0.61 | 0.610 | lost | -3.63 | -3.13 |
| 15 Nov 04:30:03 | BTC up +7.4bp 5m | 0.61 |  | 0.57 | 0.589 | missed |  | +0.12 |
| 15 Nov 04:30:03 | BTC up +7.4bp 15m | 0.67 | 0.570 | 0.57 | 0.570 | open |  | +2.06 |
| 15 Nov 04:25:58 | BTC down -6.1bp 5m | 0.62 | 0.620 | 0.53 | 0.560 | open |  | +2.26 |
| 15 Nov 04:20:14 | BTC down -6.5bp 5m | 0.65 | 0.600 | 0.56 | 0.570 | WON | +2.08 | +2.11 |
| 15 Nov 04:15:39 | BTC down -6.2bp 15m | 0.56 | 0.510 | 0.51 | 0.517 | open |  | +2.36 |
| 15 Nov 04:15:39 | BTC down -6.2bp 5m | 0.60 | 0.600 | 0.49 | 0.510 | WON | +0.43 | +2.46 |
| 15 Nov 04:11:22 | BTC up +6.2bp 5m | 0.85 |  | 0.79 | 0.827 | missed |  | +0.99 |
| 15 Nov 04:06:14 | BTC down -6.0bp 5m | 0.64 | 0.640 | 0.54 | 0.640 | WON | +1.72 | +2.21 |
| 15 Nov 04:00:34 | BTC up +6.6bp 15m | 0.49 | 0.430 | 0.41 | 0.430 | lost | -2.54 | -2.13 |
| 15 Nov 04:00:34 | BTC up +6.6bp 5m | 0.40 | 0.370 | 0.29 | 0.310 | lost | -2.08 | -1.52 |
| 15 Nov 03:55:02 | BTC down -6.8bp 5m | 0.55 | 0.500 | 0.49 | 0.490 | WON | +2.66 | +2.46 |
| 15 Nov 03:50:11 | BTC up +6.6bp 5m | 0.58 | 0.520 | 0.50 | 0.500 | WON | +2.59 | +2.41 |
| 15 Nov 03:45:37 | BTC down -6.0bp 5m | 0.71 | 0.610 | 0.62 | 0.620 | lost | -3.63 | -3.18 |
| 15 Nov 03:45:37 | BTC down -6.0bp 15m | 0.65 | 0.570 | 0.56 | 0.560 | lost | -3.34 | -2.89 |
| 15 Nov 03:40:03 | BTC down -6.9bp 5m | 0.61 | 0.560 | 0.51 | 0.513 | lost | -3.14 | -2.64 |
| 15 Nov 03:38:00 | BTC up +6.4bp 5m | 0.19 |  |  |  | refused: under $1 |  |  |
| 15 Nov 03:36:46 | BTC down -6.4bp 5m | 0.61 |  | 0.51 | 0.545 | missed |  | +2.36 |
| 15 Nov 03:30:26 | BTC up +6.0bp 5m | 0.38 | 0.330 | 0.28 | 0.280 | lost | -1.98 | -1.47 |
| 15 Nov 03:30:26 | BTC up +6.0bp 15m | 0.50 | 0.440 | 0.40 | 0.400 | lost | -2.59 | -2.08 |
| 15 Nov 03:28:02 | BTC up +6.0bp 5m | 0.80 |  |  |  | missed |  |  |
| 15 Nov 03:20:51 | BTC down -6.0bp 5m | 0.66 | 0.650 | 0.56 | 0.599 | WON | +1.70 | +2.11 |
| 15 Nov 03:15:58 | BTC down -6.9bp 15m | 0.65 | 0.590 | 0.57 | 0.570 | WON | +2.17 | +2.06 |
| 15 Nov 03:15:58 | BTC down -6.9bp 5m | 0.69 | 0.690 | 0.58 | 0.623 | WON | +1.48 | +0.59 |
| 15 Nov 03:10:14 | BTC up +6.0bp 5m | 0.65 | 0.630 | 0.55 | 0.572 | WON | +1.83 | +2.16 |
| 15 Nov 03:00:51 | BTC down -6.5bp 5m | 0.63 | 0.620 | 0.53 | 0.530 | WON | +1.85 | +2.26 |
| 15 Nov 03:00:51 | BTC down -6.5bp 15m | 0.62 | 0.550 | 0.54 |  | lost | -3.19 | -2.79 |
| 15 Nov 02:55:52 | BTC up +6.4bp 5m | 0.67 | 0.590 | 0.58 | 0.580 | WON | +2.24 | +2.01 |
| 15 Nov 02:51:10 | BTC down -6.2bp 5m | 0.23 | 0.150 | 0.13 | 0.130 | WON | +6.47 | +4.31 |
| 15 Nov 02:45:38 | BTC down -6.4bp 15m | 0.54 | 0.470 | 0.46 |  | lost | -2.79 | -2.39 |
| 15 Nov 02:45:38 | BTC down -6.4bp 5m | 0.55 | 0.520 | 0.45 | 0.451 | lost | -2.84 | -2.34 |
| 15 Nov 02:41:01 | BTC down -10.4bp 5m | 0.71 | 0.660 | 0.63 | 0.630 | WON | +1.75 | +1.77 |
| 15 Nov 02:35:57 | BTC down -6.2bp 5m | 0.82 | 0.790 | 0.74 | 0.750 | WON | +1.03 | +1.23 |
| 15 Nov 02:30:13 | BTC up +7.0bp 5m | 0.64 | 0.560 | 0.55 | 0.550 | lost | -3.29 | -2.84 |
| 15 Nov 02:30:13 | BTC up +7.0bp 15m | 0.67 | 0.580 | 0.58 | 0.580 | lost | -3.44 | -2.99 |
| 15 Nov 02:28:05 | BTC up +6.5bp 15m | 0.10 |  |  |  | refused: under $1 |  |  |
| 15 Nov 02:27:02 | BTC down -6.3bp 5m | 0.38 | 0.330 |  |  | WON | +3.78 |  |
| 15 Nov 02:25:51 | BTC up +6.1bp 5m | 0.74 |  | 0.64 | 0.650 | refused: other leg under $1 |  | -3.28 |
| 15 Nov 02:25:51 | BTC up +6.1bp 15m | 0.12 |  | 0.02 | 0.020 | refused: under $1 |  | -0.11 |
| 15 Nov 02:10:56 | BTC down -6.2bp 5m | 0.41 |  | 0.31 | 0.400 | missed |  | +3.38 |
| 15 Nov 02:02:48 | BTC down -6.0bp 15m | 0.85 | 0.840 | 0.82 | 0.820 | open |  | +0.85 |
| 15 Nov 01:50:22 | BTC up +6.2bp 5m | 0.46 |  | 0.36 | 0.363 | missed |  | +3.12 |
| 15 Nov 01:47:45 | BTC down -6.5bp 15m | 0.84 | 0.790 | 0.78 | 0.780 | WON | +1.06 | +1.04 |
| 15 Nov 01:36:01 | BTC down -6.6bp 5m | 0.67 | 0.610 | 0.57 | 0.570 | WON | +2.06 | +2.06 |
| 15 Nov 01:31:56 | BTC up +6.3bp 15m | 0.85 | 0.810 | 0.81 | 0.810 | lost | -4.30 | -4.10 |
| 15 Nov 01:28:48 | BTC down -6.1bp 5m | 0.39 |  | 0.35 | 0.350 | missed |  | +3.17 |
| 15 Nov 01:02:12 | BTC up +6.2bp 15m | 0.66 | 0.610 | 0.56 | 0.590 | WON | +2.03 | +2.11 |
| 15 Nov 01:02:12 | BTC up +6.2bp 5m | 0.70 |  | 0.60 | 0.670 | missed |  | -3.08 |
| 15 Nov 00:55:48 | BTC up +6.1bp 5m | 0.67 |  | 0.57 | 0.590 | refused: other leg under $1 |  | +2.06 |
| 15 Nov 00:55:48 | BTC up +6.1bp 15m | 0.14 |  | 0.04 |  | refused: under $1 |  | -0.21 |
| 15 Nov 00:30:49 | BTC up +6.2bp 15m | 0.81 | 0.780 | 0.71 | 0.780 | WON | +1.08 | +1.38 |
| 15 Nov 00:30:49 | BTC up +6.2bp 5m | 0.85 |  | 0.83 | 0.830 | missed |  | +0.80 |
| 15 Nov 00:23:34 | BTC down -6.3bp 5m | 0.85 |  | 0.80 |  | missed |  | +0.94 |
| 15 Nov 00:16:48 | BTC down -6.0bp 15m | 0.85 |  | 0.84 | 0.850 | missed |  | +0.75 |
| 15 Nov 00:06:58 | BTC up +6.3bp 5m | 0.83 |  | 0.83 |  | missed |  | +0.80 |
| 15 Nov 00:06:58 | BTC up +6.3bp 15m | 0.60 |  |  |  | missed |  |  |
| 14 Nov 23:46:44 | BTC down -6.2bp 15m | 0.85 | 0.770 | 0.76 | 0.760 | WON | +1.21 | +1.14 |
| 12 Nov 21:11:26 | BTC down -6.3bp 5m | 0.50 | 0.450 | 0.40 | 0.430 | lost | -2.59 | -2.08 |
| 12 Nov 21:01:38 | BTC up +6.2bp 5m | 0.29 |  |  |  | missed |  |  |
| 12 Nov 21:00:29 | BTC up +6.1bp 15m | 0.46 | 0.440 | 0.36 | 0.370 | lost | -2.39 | -1.88 |
| 12 Nov 21:00:29 | BTC up +6.1bp 5m | 0.34 |  | 0.24 | 0.317 | missed |  | -1.26 |
| 12 Nov 20:55:25 | BTC up +6.0bp 5m | 0.85 |  | 0.81 | 0.810 | missed |  | +0.90 |
| 12 Nov 20:55:25 | BTC up +6.0bp 15m | 0.85 | 0.830 |  |  | WON | +0.82 |  |
| 12 Nov 20:17:12 | BTC down -6.1bp 5m | 0.65 | 0.620 |  |  | lost | -3.33 |  |
| 12 Nov 20:17:12 | BTC down -6.1bp 15m | 0.60 | 0.530 |  |  | WON | +2.57 |  |

Read the price gap and the lost-race rate first: they decide whether v4 can work from this PC. A refused order never reached the book (Polymarket rejected it, e.g. under its $1 minimum for a marketable buy), so it is not a lost race; a refused batch also takes its healthy partner leg with it. Judge after about 50 live orders.
