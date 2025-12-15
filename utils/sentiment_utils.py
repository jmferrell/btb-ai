## 6. utils/sentiment_utils.py - Sentiment Analysis

def analyze_sentiment(text):
    """Simple sentiment analysis on text"""
    # This is a very basic version - could be replaced with a more sophisticated model
    positive_words = ["thanks", "thank", "appreciate", "good", "great", "excellent", 
                    "wonderful", "amazing", "brilliant", "kind", "help", "please",
                    "nice", "love", "enjoy", "happy", "glad"]
    
    negative_words = ["bad", "terrible", "awful", "hate", "dislike", "angry", "upset",
                    "stupid", "idiot", "fool", "annoying", "irritating", "mean", "rude"]
    
    # Count occurrences
    text_lower = text.lower()
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)
    
    # Calculate score (-1.0 to 1.0)
    total = positive_count + negative_count
    if total == 0:
        return 0.0
    
    return (positive_count - negative_count) / total