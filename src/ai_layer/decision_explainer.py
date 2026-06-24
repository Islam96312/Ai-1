from typing import Dict, Any, List

class DecisionExplainer:
    """
    Translates numeric AI decisions into human-readable explanations.
    """
    @staticmethod
    def explain(symbol: str, result: Dict[str, Any]) -> str:
        """
        Creates a detailed explanation of the trade signal.
        """
        direction = result['direction']
        decision = result['decision']
        score = result['final_score']
        components = result['components']
        reasons = result['reasons']

        if decision == "HOLD":
            return f"Holding {symbol}. The total confidence score ({score:.2f}) is too low for action."

        # Start explanation
        explanation = f"Suggested {direction} for {symbol} with {score:.2f}% confidence. "
        
        # Technical part
        if reasons:
            explanation += "Technical analysis shows: " + ", ".join(reasons) + ". "
        
        # Components analysis
        if components['technical'] > 70:
            explanation += "Strong technical setup. "
        
        if components['news'] > 60:
            explanation += "Supported by positive fundamental sentiment. "
        elif components['news'] < 40:
            explanation += "Note: Fundamental sentiment is currently bearish. "
            
        if components['risk'] < 50:
            explanation += "Caution: Higher risk detected due to upcoming economic events. "
            
        if decision == "ALERT":
            explanation += "Decision is ALERT ONLY: Setup is promising but doesn't meet full execution threshold."

        return explanation
