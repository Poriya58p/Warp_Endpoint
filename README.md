# 🌩️ WARP Endpoint Scanner

[![Workflow Status](https://github.com/Fril66/your-repo/actions/workflows/main.yml/badge.svg)](https://github.com/Fril66/your-repo/actions)
[![Python Version](https://img.shields.io/badge/python-3.10-blue)](https://www.python.org)
[![Xray Version](https://img.shields.io/badge/Xray-v1.8.23-blue)](https://github.com/XTLS/Xray-core)

🚀 **WARP Endpoint Scanner** automatically tests Cloudflare WARP endpoints to find the fastest and most reliable IPv4 addresses for your VPN setup. Updated daily with fresh results!

**Last updated**: 2025-08-06 07:29:39 IRST

## 📊 Top IPv4 Endpoints
Below are the top 10 IPv4 endpoints ranked by lowest latency and packet loss.


| Rank | Endpoint | Loss Rate (%) | Avg. Latency (ms) |
|------|----------|---------------|-------------------|
| 1 | `162.159.192.12:500` | 0.00 | 23.58 |
| 2 | `162.159.192.2:500` | 0.00 | 23.74 |
| 3 | `162.159.192.12:1701` | 0.00 | 23.93 |
| 4 | `162.159.192.5:1701` | 0.00 | 24.03 |
| 5 | `162.159.192.8:1701` | 0.00 | 24.28 |
| 6 | `162.159.192.4:500` | 0.00 | 24.39 |
| 7 | `162.159.192.14:500` | 0.00 | 24.43 |
| 8 | `162.159.192.3:2408` | 0.00 | 24.46 |
| 9 | `162.159.192.1:2408` | 0.00 | 24.54 |
| 10 | `162.159.192.7:2408` | 0.00 | 24.85 |

## 🔗 WARP Configurations
Use these pre-configured WARP setups for optimal performance. Each configuration is tested for reliability and speed.

### 1. Warp on Warp
Combines two high-performance endpoints for enhanced stability.
```mupad
warp://162.159.192.12:500/?ifp=40-80&ifps=50-100&ifpd=2-4&ifpm=m4#🇮🇷/?ifp=30-60&ifps=30-60&ifpd=4-8&ifpm=m4#🇮🇷 IP&&detour=warp://162.159.192.2:500/?ifp=40-80&ifps=50-100&ifpd=2-4&ifpm=m4#🇮🇷/?ifp=50-100&ifps=30-60&ifpd=2-4&ifpm=m4#🇩🇪 IP
```

```mupad
warp://@auto/?ifp=40-80&ifps=50-100&ifpd=2-4&ifpm=m4#🇮🇷&&detour=warp://@auto/?ifp=30-60&ifps=40-80&ifpd=1-3&ifpm=m6#🇩🇪@darkness_427
```


### 2. Warp-auto
Individual endpoints for straightforward connections.
```mupad
warp://162.159.192.12:1701/?ifp=40-80&ifps=50-100&ifpd=2-4&ifpm=m4#🇮🇷
```

```mupad
warp://162.159.192.5:1701/?ifp=40-80&ifps=50-100&ifpd=2-4&ifpm=m4#🇮🇷
```

```mupad
warp://162.159.192.8:1701/?ifp=40-80&ifps=50-100&ifpd=2-4&ifpm=m4#🇮🇷
```

```mupad
warp://162.159.192.4:500/?ifp=40-80&ifps=50-100&ifpd=2-4&ifpm=m4#🇮🇷
```


### 3. Warp-plus
Advanced configurations for premium performance.
```mupad
warp://162.159.192.14:500/?ifp=40-80&ifps=50-100&ifpd=2-4&ifpm=m4#🇮🇷&&detour=warp://162.159.192.3:2408/?ifp=50-100&ifps=30-60&ifpd=2-4&ifpm=m6#🇩🇪WoW
```

```mupad
warp://162.159.192.14:500/?ifp=50-100&ifps=30-60&ifpd=2-4&ifpm=m3#🇮🇷&&detour=warp://162.159.192.3:2408/?ifp=50-100&ifps=30-60&ifpd=2-4&ifpm=m6#🇩🇪WoW
```


## ℹ️ About
This project uses [Xray-core](https://github.com/XTLS/Xray-core) to test Cloudflare WARP endpoints. The script fetches endpoints from both a predefined API and a manual list, ensuring a comprehensive scan. Results are updated daily via GitHub Actions.

## 📬 Contact
Have questions or suggestions? Open an issue or contact the repository owner.

