import hmac
import hashlib
import time
import requests
import urllib.parse
import config
import random
import logging

# Configure logger
logger = logging.getLogger(__name__)


class BinanceAPIError(Exception):
    """Exception raised for errors returned by the Binance API."""
    def __init__(self, status_code: int, binance_code: int = None, binance_msg: str = None):
        self.status_code = status_code
        self.binance_code = binance_code
        self.binance_msg = binance_msg
        
        message = f"HTTP {status_code}"
        if binance_code is not None:
            message += f" (Binance Code: {binance_code})"
        if binance_msg is not None:
            message += f": {binance_msg}"
        
        super().__init__(message)


class BinanceClient:
    """Read-only Binance Client with self-healing geographic proxy rotation."""
    
    # Class-level cache to persist the working proxy node across separate update events
    _cached_proxy = None

    def __init__(self):
        self.api_key = config.BINANCE_API_KEY
        self.api_secret = config.BINANCE_API_SECRET
        self.base_url = config.BINANCE_BASE_URL

    def _sign(self, query_string: str) -> str:
        """Sign a query string using HMAC-SHA256 and the API secret."""
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _get_proxy_list(self) -> list:
        """Fetch a pre-validated list of working, active HTTPS proxies."""
        url = "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/https.txt"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                # Split lines, remove whitespace, and shuffle to distribute server load
                proxies = [line.strip() for line in response.text.split('\n') if line.strip()]
                random.shuffle(proxies)
                return proxies
        except Exception as e:
            logger.error(f"Failed to fetch public proxy list: {e}")
        return []

    def get_deposit_history(self, limit: int = 20) -> list:
        """
        Fetch recent Binance deposit history.
        Uses signature authentication and a self-healing proxy tunnel system.
        """
        endpoint = "/sapi/v1/capital/deposit/hisrec"
        url = f"{self.base_url}{endpoint}"

        # Generate a standard current timestamp in milliseconds
        timestamp = int(time.time() * 1000)

        # Prepare parameters for the request
        params = {
            "timestamp": timestamp,
            "recvWindow": 60000,  # 60s request window to reduce timestamp drift issues
            "limit": limit
        }

        # Encode parameters and create request signature
        query_string = urllib.parse.urlencode(params)
        signature = self._sign(query_string)
        params["signature"] = signature

        # Setup headers
        headers = {
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/json"
        }

        # 1. Try using the cached proxy node first for instant zero-latency responses
        if BinanceClient._cached_proxy:
            logger.info(f"Attempting to query using cached proxy: {BinanceClient._cached_proxy}")
            proxies = {
                "http": f"http://{BinanceClient._cached_proxy}",
                "https": f"http://{BinanceClient._cached_proxy}"
            }
            try:
                response = requests.get(url, params=params, headers=headers, proxies=proxies, timeout=5)
                return self._parse_response(response)
            except Exception as e:
                logger.warning(f"Cached proxy node {BinanceClient._cached_proxy} failed: {e}. Invalidating cache.")
                BinanceClient._cached_proxy = None

        # 2. Try direct connection first (to ensure fallback readiness)
        try:
            logger.info("Attempting direct connection to Binance...")
            response = requests.get(url, params=params, headers=headers, timeout=5)
            return self._parse_response(response)
        except BinanceAPIError as e:
            # Check if blocked due to datacenter IP or terms eligibility
            if e.status_code in [403, 451] or "restricted location" in str(e).lower() or "eligibility" in str(e).lower():
                logger.warning("Direct connection blocked by geographical/datacenter restrictions. Initiating proxy rotation...")
            else:
                # Propagate standard API errors directly
                raise e
        except requests.exceptions.RequestException as e:
            logger.warning(f"Direct connection failed or timed out: {e}. Initiating proxy rotation...")

        # 3. If direct connection fails/blocked, retrieve and test proxy list
        logger.info("Retrieving updated public proxy list...")
        proxy_candidates = self._get_proxy_list()
        if not proxy_candidates:
            raise BinanceAPIError(
                status_code=502,
                binance_msg="Binance API is restricted here, and we failed to fetch active proxy list to bypass."
            )

        logger.info(f"Found {len(proxy_candidates)} candidate nodes. Initiating connection testing...")
        
        # Test candidate nodes sequentially with a low timeout to keep the command fast and responsive
        for proxy_ip in proxy_candidates[:40]:  # Try up to 40 candidates
            proxies = {
                "http": f"http://{proxy_ip}",
                "https": f"http://{proxy_ip}"
            }
            try:
                logger.info(f"Testing route via proxy node: {proxy_ip}")
                response = requests.get(url, params=params, headers=headers, proxies=proxies, timeout=4)
                data = self._parse_response(response)
                
                # Cache the successful proxy to avoid searching on subsequent checks
                BinanceClient._cached_proxy = proxy_ip
                logger.info(f"Successfully bypassed restricted block! Route cached via proxy: {proxy_ip}")
                return data
            except Exception as e:
                logger.debug(f"Proxy node {proxy_ip} failed connection: {e}")
                continue

        raise BinanceAPIError(
            status_code=502,
            binance_msg="All available proxy routes timed out or were blocked. Please try again in a few moments."
        )

    def get_pay_history(self, limit: int = 20) -> list:
        """
        Fetch recent Binance Pay transaction history.
        Uses signature authentication and a self-healing proxy tunnel system.
        """
        endpoint = "/sapi/v1/pay/transactions"
        url = f"{self.base_url}{endpoint}"

        # Generate a standard current timestamp in milliseconds
        timestamp = int(time.time() * 1000)

        # Prepare parameters for the request
        params = {
            "timestamp": timestamp,
            "recvWindow": 60000,  # 60s request window to reduce timestamp drift issues
            "limit": limit
        }

        # Encode parameters and create request signature
        query_string = urllib.parse.urlencode(params)
        signature = self._sign(query_string)
        params["signature"] = signature

        # Setup headers
        headers = {
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/json"
        }

        # Helper to extract pay transaction list from response dictionary
        def extract_list(res_data):
            if isinstance(res_data, dict):
                return res_data.get("data", [])
            return []

        # 1. Try using the cached proxy node first for instant zero-latency responses
        if BinanceClient._cached_proxy:
            logger.info(f"Attempting to query Pay using cached proxy: {BinanceClient._cached_proxy}")
            proxies = {
                "http": f"http://{BinanceClient._cached_proxy}",
                "https": f"http://{BinanceClient._cached_proxy}"
            }
            try:
                response = requests.get(url, params=params, headers=headers, proxies=proxies, timeout=5)
                res_data = self._parse_response(response)
                return extract_list(res_data)
            except Exception as e:
                logger.warning(f"Cached proxy node {BinanceClient._cached_proxy} failed for Pay: {e}. Invalidating cache.")
                BinanceClient._cached_proxy = None

        # 2. Try direct connection first (to ensure fallback readiness)
        try:
            logger.info("Attempting direct connection for Pay to Binance...")
            response = requests.get(url, params=params, headers=headers, timeout=5)
            res_data = self._parse_response(response)
            return extract_list(res_data)
        except BinanceAPIError as e:
            # Check if blocked due to datacenter IP or terms eligibility
            if e.status_code in [403, 451] or "restricted location" in str(e).lower() or "eligibility" in str(e).lower():
                logger.warning("Direct Pay connection blocked by geographical/datacenter restrictions. Initiating proxy rotation...")
            else:
                # Propagate standard API errors directly
                raise e
        except requests.exceptions.RequestException as e:
            logger.warning(f"Direct Pay connection failed or timed out: {e}. Initiating proxy rotation...")

        # 3. If direct connection fails/blocked, retrieve and test proxy list
        logger.info("Retrieving updated public proxy list for Pay...")
        proxy_candidates = self._get_proxy_list()
        if not proxy_candidates:
            raise BinanceAPIError(
                status_code=502,
                binance_msg="Binance API is restricted here, and we failed to fetch active proxy list to bypass Pay check."
            )

        logger.info(f"Found {len(proxy_candidates)} candidate nodes. Initiating connection testing for Pay...")
        
        # Test candidate nodes sequentially with a low timeout to keep the command fast and responsive
        for proxy_ip in proxy_candidates[:40]:  # Try up to 40 candidates
            proxies = {
                "http": f"http://{proxy_ip}",
                "https": f"http://{proxy_ip}"
            }
            try:
                logger.info(f"Testing Pay route via proxy node: {proxy_ip}")
                response = requests.get(url, params=params, headers=headers, proxies=proxies, timeout=4)
                res_data = self._parse_response(response)
                
                # Cache the successful proxy to avoid searching on subsequent checks
                BinanceClient._cached_proxy = proxy_ip
                logger.info(f"Successfully bypassed restricted block for Pay! Route cached via proxy: {proxy_ip}")
                return extract_list(res_data)
            except Exception as e:
                logger.debug(f"Proxy node {proxy_ip} failed connection for Pay: {e}")
                continue

        raise BinanceAPIError(
            status_code=502,
            binance_msg="All available proxy routes timed out or were blocked for Pay. Please try again in a few moments."
        )

    def _parse_response(self, response: requests.Response) -> list:
        """Helper to parse API responses and raise custom exceptions on errors."""
        if response.status_code == 200:
            try:
                return response.json()
            except ValueError:
                raise BinanceAPIError(
                    status_code=200,
                    binance_msg="Binance response was successful, but could not parse body as JSON."
                )
        else:
            # Parse error payload
            binance_code = None
            binance_msg = None
            try:
                err_data = response.json()
                binance_code = err_data.get("code")
                binance_msg = err_data.get("msg")
            except ValueError:
                binance_msg = response.text

            raise BinanceAPIError(
                status_code=response.status_code,
                binance_code=binance_code,
                binance_msg=binance_msg
            )
