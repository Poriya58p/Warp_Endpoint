import base64
import datetime
import json
import os
import random
import time
import requests
import nacl.public
import nacl.utils
import nacl.bindings
import subprocess
import platform
import concurrent.futures
from typing import List, Dict, Any, Tuple, Optional

# --- Constants ---
WARP_API_URL = "https://api.cloudflareclient.com/v0a4005/reg"
USER_AGENT = "insomnia/8.6.1"
ENDPOINT_API_URL = "https://raw.githubusercontent.com/ircfspace/endpoint/refs/heads/main/ip.json"

# Manual IPv4 prefixes and ports (replace with your own list)
IPV4_PREFIXES = [
    "162.159.192.", "162.159.193.", "162.159.195.", 
    "188.114.96.", "188.114.97.", "188.114.98.", "188.114.99."
]
PORTS = [80, 443, 8080, 8880, 500, 1701, 2408]

CORE_INIT_PORT = 10800
CORE_DIR = "Files/xray_core_temp_files"
XRAY_CONFIG_FILE = os.path.join(CORE_DIR, "config.json")
XRAY_LOG_STDOUT_FILE = os.path.join(CORE_DIR, "xray_stdout.log")
XRAY_LOG_STDERR_FILE = os.path.join(CORE_DIR, "xray_stderr.log")

if platform.system() == "Windows":
    XRAY_EXECUTABLE_PATH = "Files/xray.exe"
else:
    XRAY_EXECUTABLE_PATH = "Files/xray"

TEST_URL = "http://www.gstatic.com/generate_204"
TEST_TRIES = 3
TEST_TIMEOUT_SECONDS = 2
MAX_CONCURRENT_TESTS = 10  # Reduced to avoid broken pipe errors

ScanResult = Tuple[str, float, float]  # endpoint, avg_latency_ms, loss_rate_percent

def generate_wireguard_keypair() -> Tuple[str, str]:
    """Generates a WireGuard key pair."""
    private_key_bytes = bytearray(os.urandom(32))
    private_key_bytes[0] &= 248
    private_key_bytes[31] &= 127
    private_key_bytes[31] |= 64
    public_key_bytes = nacl.bindings.crypto_scalarmult_base(bytes(private_key_bytes))
    private_key_b64 = base64.b64encode(bytes(private_key_bytes)).decode('utf-8')
    public_key_b64 = base64.b64encode(public_key_bytes).decode('utf-8')
    return public_key_b64, private_key_b64

def fetch_warp_config_from_api(public_key_b64: str) -> Optional[Dict[str, Any]]:
    """Fetches WARP configuration from Cloudflare API."""
    payload = {
        "install_id": "", "fcm_token": "",
        "tos": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "type": "Android", "model": "PC", "locale": "en_US", "warp_enabled": True,
        "key": public_key_b64,
    }
    headers = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
    try:
        response = requests.post(WARP_API_URL, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        print("Successfully fetched WARP config from API.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching WARP config: {e}")
        return None

def extract_warp_parameters(config_data: Dict[str, Any], client_private_key_b64: str) -> Optional[Dict[str, Any]]:
    """Extracts necessary parameters for Xray from WARP configuration."""
    try:
        conf = config_data['config']
        client_ipv6 = conf['interface']['addresses']['v6']
        if not client_ipv6.endswith("/128"):
            client_ipv6 += "/128"
        client_id_b64 = conf['client_id']
        reserved_bytes = list(base64.b64decode(client_id_b64))
        if not conf['peers']:
            print("Error: No peers found in WARP config.")
            return None
        peer_public_key = conf['peers'][0]['public_key']
        params = {
            "PrivateKey": client_private_key_b64,
            "IPv6": client_ipv6,
            "Reserved": reserved_bytes,
            "PublicKey": peer_public_key
        }
        print(f"Successfully extracted WARP parameters (Client IPv6: {params['IPv6']}).")
        return params
    except (KeyError, IndexError) as e:
        print(f"Error extracting WARP parameters: Missing key or peer - {e}")
        return None

def get_warp_params_for_xray() -> Optional[Dict[str, Any]]:
    """Manages the entire process of obtaining WARP parameters."""
    client_public_key, client_private_key = generate_wireguard_keypair()
    print(f"Generated WireGuard Keys. Client Public Key: {client_public_key[:20]}...")
    config_data = fetch_warp_config_from_api(client_public_key)
    if not config_data:
        return None
    return extract_warp_parameters(config_data, client_private_key)

def fetch_endpoints_from_api(api_url: str) -> List[str]:
    """Fetches IPv4 endpoints from the provided API."""
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(api_url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        ipv4_endpoints = data.get("ipv4", [])
        valid_ipv4_endpoints = []
        for endpoint in ipv4_endpoints:
            try:
                ip, port = endpoint.split(":")
                octets = ip.split(".")
                if len(octets) == 4 and all(o.isdigit() and 0 <= int(o) <= 255 for o in octets):
                    valid_ipv4_endpoints.append(endpoint)
                else:
                    print(f"Skipping invalid IPv4 endpoint: {endpoint}")
            except ValueError:
                print(f"Skipping invalid IPv4 endpoint: {endpoint}")
        print(f"Fetched {len(valid_ipv4_endpoints)} valid IPv4 endpoints from API.")
        return valid_ipv4_endpoints
    except requests.exceptions.RequestException as e:
        print(f"Error fetching endpoints from API: {e}")
        return []

def generate_manual_endpoints() -> List[str]:
    """Generates IPv4 endpoints from predefined prefixes and ports."""
    manual_endpoints = []
    for prefix in IPV4_PREFIXES:
        for i in range(1, 255):  # Iterate over possible last octet
            for port in PORTS:
                endpoint = f"{prefix}{i}:{port}"
                manual_endpoints.append(endpoint)
    print(f"Generated {len(manual_endpoints)} manual IPv4 endpoints.")
    return manual_endpoints[:100]  # Limit to 100 endpoints to speed up testing

def build_xray_config_json(candidate_endpoints: List[str], warp_params: Dict[str, Any]) -> Dict[str, Any]:
    """Creates the JSON configuration file for Xray."""
    inbounds = []
    outbounds = [{"protocol": "freedom", "settings": {}, "tag": "direct"}]
    routing_rules = [{"type": "field", "outboundTag": "direct", "protocol": ["dns"]}]
    for i, endpoint_addr_port in enumerate(candidate_endpoints):
        inbound_tag = f"http-in-{i+1}"
        outbound_tag = f"proxy-{i+1}"
        local_proxy_port = CORE_INIT_PORT + i
        inbounds.append({
            "listen": "127.0.0.1", "port": local_proxy_port, "protocol": "http",
            "tag": inbound_tag, "settings": {"timeout": 120}
        })
        outbounds.append({
            "protocol": "wireguard",
            "settings": {
                "secretKey": warp_params["PrivateKey"],
                "address": ["172.16.0.2/32", warp_params["IPv6"]],
                "peers": [{
                    "publicKey": warp_params["PublicKey"],
                    "endpoint": endpoint_addr_port,
                    "keepAlive": 25
                }],
                "mtu": 1280,
                "reserved": warp_params["Reserved"]
            },
            "tag": outbound_tag
        })
        routing_rules.append({
            "type": "field", "inboundTag": [inbound_tag], "outboundTag": outbound_tag
        })
    xray_log_config_access = os.path.join(CORE_DIR, "access.log")
    xray_log_config_error = os.path.join(CORE_DIR, "error.log")
    return {
        "log": {"access": xray_log_config_access, "error": xray_log_config_error, "loglevel": "info"},
        "dns": {"servers": ["1.1.1.1", "8.8.8.8", "1.0.0.1"]},
        "inbounds": inbounds, "outbounds": outbounds,
        "routing": {"domainStrategy": "AsIs", "rules": routing_rules}
    }

def test_single_proxy(original_endpoint: str, proxy_address: str, target_url: str, num_tries: int, timeout: int) -> Optional[ScanResult]:
    """Tests a single proxy and returns (original_endpoint, avg_latency_ms, loss_rate_percent) or None."""
    success_count = 0
    latencies: List[float] = []
    for i in range(num_tries):
        start_time = time.monotonic()
        try:
            response = requests.head(
                target_url,
                proxies={"http": proxy_address, "https": proxy_address},
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            latency_ms = (time.monotonic() - start_time) * 1000
            if response.status_code == 204:
                success_count += 1
                latencies.append(latency_ms)
        except requests.exceptions.Timeout:
            pass
        except requests.exceptions.RequestException:
            pass
        if i < num_tries - 1:
            time.sleep(0.5)  # Increased delay to reduce broken pipe errors
    if not latencies:
        return None
    avg_latency = sum(latencies) / len(latencies)
    loss_rate = (num_tries - success_count) / num_tries * 100.0
    return original_endpoint, avg_latency, loss_rate

def main():
    if not os.path.exists(XRAY_EXECUTABLE_PATH):
        print(f"Error: Xray executable not found at '{XRAY_EXECUTABLE_PATH}'.")
        print("Please download Xray and place it in the correct path or update the XRAY_EXECUTABLE_PATH variable.")
        return

    os.makedirs(CORE_DIR, exist_ok=True)

    print("1. Fetching WARP parameters...")
    warp_params = get_warp_params_for_xray()
    if not warp_params:
        print("Failed to fetch WARP parameters. Exiting.")
        return
    
    print(f"Received WARP IPv6 parameter: {warp_params.get('IPv6')}")

    print("\n2. Fetching IP endpoints from API and manual list...")
    api_endpoints = fetch_endpoints_from_api(ENDPOINT_API_URL)
    manual_endpoints = generate_manual_endpoints()
    candidate_endpoints = list(set(api_endpoints + manual_endpoints))  # Combine and remove duplicates
    if not candidate_endpoints:
        print("No endpoints received. Exiting.")
        return
    random.shuffle(candidate_endpoints)
    print(f"Fetched {len(api_endpoints)} API endpoints and {len(manual_endpoints)} manual endpoints. Total: {len(candidate_endpoints)} IPv4 endpoints.")

    print(f"\n3. Building Xray configuration for {len(candidate_endpoints)} endpoints...")
    xray_json_config = build_xray_config_json(candidate_endpoints, warp_params)
    try:
        with open(XRAY_CONFIG_FILE, "w") as f:
            json.dump(xray_json_config, f, indent=2)
        print(f"Xray configuration written to {XRAY_CONFIG_FILE}.")
    except IOError as e:
        print(f"Error writing Xray configuration file: {e}")
        return

    print("\n4. Starting Xray core...")
    xray_process: Optional[subprocess.Popen] = None
    
    try:
        with open(XRAY_LOG_STDOUT_FILE, "wb") as stdout_f, open(XRAY_LOG_STDERR_FILE, "wb") as stderr_f:
            xray_process = subprocess.Popen(
                [XRAY_EXECUTABLE_PATH, "-c", XRAY_CONFIG_FILE],
                stdout=stdout_f, stderr=stderr_f
            )
        print(f"Xray process started with PID: {xray_process.pid}. Waiting for initialization...")
        time.sleep(6)
    except FileNotFoundError:
        print(f"Error: Xray executable not found at '{XRAY_EXECUTABLE_PATH}'.")
        return
    except Exception as e:
        print(f"Error starting Xray: {e}")
        if xray_process:
            xray_process.kill()
        return

    print(f"\n5. Testing {len(candidate_endpoints)} endpoints with max {MAX_CONCURRENT_TESTS} concurrent tests...")
    
    tasks_completed = 0
    all_tested_results: List[ScanResult] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_TESTS) as executor:
        future_to_endpoint_test = {}
        for i, original_endpoint_candidate in enumerate(candidate_endpoints):
            local_proxy_port = CORE_INIT_PORT + i
            proxy_url_for_test = f"http://127.0.0.1:{local_proxy_port}"
            future = executor.submit(test_single_proxy, original_endpoint_candidate, proxy_url_for_test, TEST_URL, TEST_TRIES, TEST_TIMEOUT_SECONDS)
            future_to_endpoint_test[future] = original_endpoint_candidate

        for future in concurrent.futures.as_completed(future_to_endpoint_test):
            original_endpoint_tested = future_to_endpoint_test[future]
            try:
                result: Optional[ScanResult] = future.result()
                if result:
                    all_tested_results.append(result)
            except Exception as exc:
                print(f"    Error during test for {original_endpoint_tested}: {exc}")
            tasks_completed += 1
            if tasks_completed % (len(candidate_endpoints) // 20 or 1) == 0 or tasks_completed == len(candidate_endpoints):
                print(f"   Test progress: {tasks_completed}/{len(candidate_endpoints)} completed.")

    print("\n6. Stopping Xray core...")
    if xray_process:
        xray_process.terminate()
        try:
            xray_process.wait(timeout=10)
            print("Xray process terminated.")
        except subprocess.TimeoutExpired:
            print("Xray process did not terminate in time, killing...")
            xray_process.kill()
            xray_process.wait()
            print("Xray process killed.")

    print("\n7. Processing and saving results to README.md...")
    
    ipv4_results = all_tested_results
    ipv4_results.sort(key=lambda x: (x[1] if x[1] != -1 else float('inf'), x[2]))

    # Convert UTC to IRST (UTC+3:30)
    utc_time = datetime.datetime.now(datetime.timezone.utc)
    irst_offset = datetime.timedelta(hours=3, minutes=30)
    irst_time = utc_time + irst_offset

    readme_content = [
        "# 🌩️ WARP Endpoint Scanner",
        "",
        "[![Workflow Status](https://github.com/your-username/your-repo/actions/workflows/main.yml/badge.svg)](https://github.com/your-username/your-repo/actions)",
        "[![Python Version](https://img.shields.io/badge/python-3.10-blue)](https://www.python.org)",
        "[![Xray Version](https://img.shields.io/badge/Xray-v1.8.23-blue)](https://github.com/XTLS/Xray-core)",
        "",
        "🚀 **WARP Endpoint Scanner** automatically tests Cloudflare WARP endpoints to find the fastest and most reliable IPv4 addresses for your VPN setup. Updated daily with fresh results!",
        "",
        f"**Last updated**: {irst_time.strftime('%Y-%m-%d %H:%M:%S IRST')}",
        "",
        "## 📊 Top IPv4 Endpoints",
        "Below are the top 10 IPv4 endpoints ranked by lowest latency and packet loss.",
        ""
    ]

    num_to_output = 10
    valid_ipv4_results = [r for r in ipv4_results if r[1] != -1][:num_to_output]
    if valid_ipv4_results:
        if len(valid_ipv4_results) < num_to_output:
            readme_content.append(f"> ⚠️ *Note: Only {len(valid_ipv4_results)} suitable IPv4 endpoints were found.*")
        readme_content.append("")
        readme_content.append("| Rank | Endpoint | Loss Rate (%) | Avg. Latency (ms) |")
        readme_content.append("|------|----------|---------------|-------------------|")
        for i, res in enumerate(valid_ipv4_results, 1):
            readme_content.append(f"| {i} | `{res[0]}` | {res[2]:.2f} | {res[1]:.2f} |")
    else:
        readme_content.append("> 🚫 *No suitable IPv4 endpoints were found.*")

    readme_content.extend([
        "",
        "## 🔗 WARP Configurations",
        "Use these pre-configured WARP setups for optimal performance. Each configuration is tested for reliability and speed.",
        "",
        "### 1. Warp on Warp",
        "Combines two high-performance endpoints for enhanced stability."
    ])

    if len(valid_ipv4_results) >= 2:
        ip_port_1 = valid_ipv4_results[0][0]
        ip_port_2 = valid_ipv4_results[1][0]
        readme_content.extend([
            "```mupad",
            f"warp://{ip_port_1}/?ifp=40-80&ifps=50-100&ifpd=2-4&ifpm=m4#🇮🇷/?ifp=30-60&ifps=30-60&ifpd=4-8&ifpm=m4#🇮🇷 IP&&detour=warp://{ip_port_2}/?ifp=40-80&ifps=50-100&ifpd=2-4&ifpm=m4#🇮🇷/?ifp=50-100&ifps=30-60&ifpd=2-4&ifpm=m4#🇩🇪 IP",
            "```",
            "",
            "```mupad",
            f"warp://@auto/?ifp=40-80&ifps=50-100&ifpd=2-4&ifpm=m4#🇮🇷&&detour=warp://@auto/?ifp=30-60&ifps=40-80&ifpd=1-3&ifpm=m6#🇩🇪@darkness_427",
            "```",
            ""
        ])
    else:
        readme_content.append("> 🚫 *Not enough IPv4 endpoints available for Warp on Warp configurations.*")

    readme_content.extend([
        "",
        "### 2. Warp-auto",
        "Individual endpoints for straightforward connections."
    ])

    warp_auto_configs = []
    for i in range(2, min(6, len(valid_ipv4_results))):
        warp_auto_configs.append(
            f"```mupad\n"
            f"warp://{valid_ipv4_results[i][0]}/?ifp=40-80&ifps=50-100&ifpd=2-4&ifpm=m4#🇮🇷\n"
            f"```\n"
        )
    if warp_auto_configs:
        readme_content.extend(warp_auto_configs)
    else:
        readme_content.append("> 🚫 *Not enough IPv4 endpoints available for Warp-auto configurations.*")

    readme_content.extend([
        "",
        "### 3. Warp-plus",
        "Advanced configurations for premium performance."
    ])

    if len(valid_ipv4_results) >= 2:
        ip_port_3 = valid_ipv4_results[min(6, len(valid_ipv4_results)-1)][0]
        ip_port_4 = valid_ipv4_results[min(7, len(valid_ipv4_results)-1)][0]
        readme_content.extend([
            "```mupad",
            f"warp://{ip_port_3}/?ifp=40-80&ifps=50-100&ifpd=2-4&ifpm=m4#🇮🇷&&detour=warp://{ip_port_4}/?ifp=50-100&ifps=30-60&ifpd=2-4&ifpm=m6#🇩🇪WoW",
            "```",
            "",
            "```mupad",
            f"warp://{ip_port_3}/?ifp=50-100&ifps=30-60&ifpd=2-4&ifpm=m3#🇮🇷&&detour=warp://{ip_port_4}/?ifp=50-100&ifps=30-60&ifpd=2-4&ifpm=m6#🇩🇪WoW",
            "```",
            ""
        ])
    else:
        readme_content.append("> 🚫 *Not enough IPv4 endpoints available for Warp-plus configurations.*")

    readme_content.extend([
        "",
        "## ℹ️ About",
        "This project uses [Xray-core](https://github.com/XTLS/Xray-core) to test Cloudflare WARP endpoints. The script fetches endpoints from both a predefined API and a manual list, ensuring a comprehensive scan. Results are updated daily via GitHub Actions.",
        "",
        "## 📬 Contact",
        "Have questions or suggestions? Open an issue or contact the repository owner.",
        ""
    ])

    output_filename_md = "README.md"
    try:
        with open(output_filename_md, "w", encoding='utf-8') as f:
            for line in readme_content:
                f.write(line + "\n")
        print(f"\nResults successfully written to {output_filename_md}.")
        print(f"Total working IPv4 endpoints found: {len(valid_ipv4_results)}")
    except IOError as e:
        print(f"Error writing README.md file: {e}")

    try:
        if os.path.exists(XRAY_CONFIG_FILE):
            os.remove(XRAY_CONFIG_FILE)
    except OSError as e:
        print(f"Error cleaning up temporary config file: {e}")

if __name__ == "__main__":
    main()
