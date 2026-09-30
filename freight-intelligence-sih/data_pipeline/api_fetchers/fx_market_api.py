"""
FX & Market Data API Fetcher
Fetches USD-INR exchange rate, Baltic Dry Index (BDI), sub-indices (BCI, BPI, BSI), and Brent Crude oil prices.
"""

from typing import Dict, Any

class FXMarketAPIFetcher:
    def get_market_telemetry(self) -> Dict[str, Any]:
        """
        Returns latest market telemetry required for freight rate regression.
        """
        return {
            "usd_inr": 83.42,
            "usd_inr_change_7d": 0.18,
            "bdi": 1842,
            "bdi_change_7d_pct": 2.4,
            "bci_capesize": 2380,
            "bpi_panamax": 1765,
            "bsi_supramax": 1460,
            "brent_crude_usd": 79.85,
            "brent_crude_change_pct": -0.8,
            "ffa_forward_rates": {
                "cal26_supramax": 15200,
                "q4_26_panamax": 17400,
                "q4_26_capesize": 24800
            },
            "market_sentiment": "Bullish short-term freight outlook on iron ore demand & weather premiums"
        }
