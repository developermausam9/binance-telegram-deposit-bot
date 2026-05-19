import hmac
import hashlib
import time
import requests
import urllib.parse
import config

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
    """Read-only Binance Client for checking deposit history."""
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

    def get_deposit_history(self, limit: int = 20) -> list:
        """
        Fetch recent Binance deposit history.
        Uses signature authentication and a robust timestamp check.
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
        
        # Append signature to parameters
        params["signature"] = signature

        # Setup headers
        headers = {
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/json"
        }

        try:
            # Execute HTTP GET request
            response = requests.get(url, params=params, headers=headers, timeout=15)
        except requests.exceptions.RequestException as e:
            raise BinanceAPIError(
                status_code=500,
                binance_msg=f"Network error when communicating with Binance: {str(e)}"
            )

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
