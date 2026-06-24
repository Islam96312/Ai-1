from typing import List, Tuple

class SymbolMapper:
    """
    Maps trading symbols to their constituent currencies.
    Example: 'EURUSD' -> ('EUR', 'USD')
    """
    @staticmethod
    def get_currencies(symbol: str) -> Tuple[str, str]:
        """
        Splits a symbol into base and quote currency.
        Handles common formats like EURUSD, XAUUSD, GBPJPY.
        """
        symbol = symbol.upper()
        # Standard 6-character symbols (e.g., EURUSD)
        if len(symbol) == 6:
            return symbol[:3], symbol[3:]
        
        # Handle Gold (XAUUSD) or Silver (XAGUSD)
        if symbol.startswith("XAU") or symbol.startswith("XAG"):
            return symbol[:3], symbol[3:]
        
        # Fallback for symbols like BTCUSD
        if "USD" in symbol:
            return symbol.replace("USD", ""), "USD"
        
        # Default fallback
        return symbol, "USD"

    @staticmethod
    def get_all_relevant_currencies(symbols: List[str]) -> List[str]:
        """
        Returns a unique list of all currencies involved in the monitored symbols.
        """
        currencies = set()
        for s in symbols:
            base, quote = SymbolMapper.get_currencies(s)
            currencies.add(base)
            currencies.add(quote)
        return list(currencies)
