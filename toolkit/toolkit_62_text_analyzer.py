"""
toolkit_62_text_analyzer.py
Analyze text documents: readability scores, sentiment indicators,
keyword extraction, language detection, summarization helpers, and
text statistics. Stdlib only with optional nltk/textblob soft-imports.
"""
from __future__ import annotations
import re
import math
import collections
from typing import Any, Dict, List

try:
    from textblob import TextBlob
    HAS_TEXTBLOB = True
except ImportError:
    HAS_TEXTBLOB = False

try:
    import nltk
    HAS_NLTK = True
except ImportError:
    HAS_NLTK = False

def count_text_stats(text: str) -> Dict[str, Any]:
    try:
        words = re.findall(r"\b\w+\b", text)
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        return {"success": True, "data": {
            "characters": len(text),
            "characters_no_spaces": len(text.replace(" ", "")),
            "words": len(words),
            "sentences": len(sentences),
            "paragraphs": len(paragraphs),
            "avg_word_length": round(sum(len(w) for w in words) / max(len(words), 1), 2),
            "avg_sentence_length": round(len(words) / max(len(sentences), 1), 2)
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def flesch_reading_ease(text: str) -> Dict[str, Any]:
    """Flesch Reading Ease score. Higher = easier to read (0-100)."""
    try:
        words = re.findall(r"\b[a-zA-Z]+\b", text)
        sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
        if not words or not sentences:
            return {"success": False, "data": None, "error": "Insufficient text"}
        def count_syllables(word):
            word = word.lower()
            count = len(re.findall(r"[aeiou]+", word))
            if word.endswith("e") and count > 1:
                count -= 1
            return max(1, count)
        total_syllables = sum(count_syllables(w) for w in words)
        score = 206.835 - 1.015 * (len(words) / len(sentences)) - 84.6 * (total_syllables / len(words))
        score = round(max(0, min(100, score)), 1)
        if score >= 90: level = "Very Easy"
        elif score >= 80: level = "Easy"
        elif score >= 70: level = "Fairly Easy"
        elif score >= 60: level = "Standard"
        elif score >= 50: level = "Fairly Difficult"
        elif score >= 30: level = "Difficult"
        else: level = "Very Difficult"
        return {"success": True, "data": {"score": score, "level": level}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_keyword_frequency(text: str, top_n: int = 20, min_length: int = 4) -> Dict[str, Any]:
    try:
        STOPWORDS = {"the","a","an","and","or","but","is","are","was","were","be","been","being",
                     "have","has","had","do","does","did","will","would","could","should","may","might",
                     "shall","can","need","dare","ought","used","of","to","in","for","on","with","at",
                     "by","from","up","about","into","through","during","before","after","above","below",
                     "between","out","off","over","under","again","further","then","once","this","that",
                     "these","those","i","you","he","she","it","we","they","what","which","who","whom",
                     "not","no","nor","so","yet","both","either","neither","such","than","too","very"}
        words = re.findall(r"\b[a-z]+\b", text.lower())
        filtered = [w for w in words if len(w) >= min_length and w not in STOPWORDS]
        freq = collections.Counter(filtered)
        return {"success": True, "data": dict(freq.most_common(top_n)), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_bigrams(text: str, top_n: int = 10) -> Dict[str, Any]:
    try:
        words = re.findall(r"\b[a-z]+\b", text.lower())
        bigrams = [(words[i], words[i+1]) for i in range(len(words)-1)]
        freq = collections.Counter(bigrams)
        return {"success": True, "data": {" ".join(k): v for k, v in freq.most_common(top_n)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def detect_language_simple(text: str) -> Dict[str, Any]:
    """Very basic language detection by common word patterns."""
    try:
        text_lower = text.lower()
        scores = {
            "english": sum(1 for w in ["the","and","is","in","that","for","it","with","as","on"] if " " + w + " " in text_lower),
            "spanish": sum(1 for w in ["el","la","los","las","de","en","que","y","es","se"] if " " + w + " " in text_lower),
            "french": sum(1 for w in ["le","la","les","de","du","en","que","et","est","un"] if " " + w + " " in text_lower),
            "german": sum(1 for w in ["der","die","das","und","in","ist","von","zu","den","mit"] if " " + w + " " in text_lower),
        }
        best = max(scores, key=lambda x: scores[x])
        return {"success": True, "data": {"detected": best, "scores": scores}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_sentiment_textblob(text: str) -> Dict[str, Any]:
    try:
        if not HAS_TEXTBLOB:
            return {"success": False, "data": None, "error": "textblob not installed (pip install textblob)"}
        blob = TextBlob(text)
        sentiment = blob.sentiment
        label = "positive" if sentiment.polarity > 0.1 else "negative" if sentiment.polarity < -0.1 else "neutral"
        return {"success": True, "data": {
            "polarity": round(sentiment.polarity, 4),
            "subjectivity": round(sentiment.subjectivity, 4),
            "label": label
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_simple_sentiment(text: str) -> Dict[str, Any]:
    """Basic sentiment without external libs."""
    try:
        positive_words = {"good","great","excellent","amazing","wonderful","fantastic","happy","love","like","best","nice",
                          "awesome","outstanding","perfect","brilliant","superb","positive","beautiful","enjoy","helpful"}
        negative_words = {"bad","terrible","awful","horrible","hate","worst","poor","negative","wrong","fail","ugly",
                          "broken","useless","disappointing","frustrating","annoying","boring","sad","angry","error"}
        words = set(re.findall(r"\b[a-z]+\b", text.lower()))
        pos_count = len(words & positive_words)
        neg_count = len(words & negative_words)
        if pos_count > neg_count: label = "positive"
        elif neg_count > pos_count: label = "negative"
        else: label = "neutral"
        return {"success": True, "data": {"label": label, "positive_hits": pos_count, "negative_hits": neg_count}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def extract_sentences(text: str) -> Dict[str, Any]:
    try:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        return {"success": True, "data": {"count": len(sentences), "sentences": sentences}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_longest_words(text: str, top_n: int = 10) -> Dict[str, Any]:
    try:
        words = list(set(re.findall(r"\b[a-zA-Z]+\b", text)))
        words.sort(key=len, reverse=True)
        return {"success": True, "data": words[:top_n], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def compare_texts(text1: str, text2: str) -> Dict[str, Any]:
    """Compare two texts for similarity and differences."""
    try:
        import difflib
        ratio = difflib.SequenceMatcher(None, text1, text2).ratio()
        words1 = set(re.findall(r"\b[a-z]+\b", text1.lower()))
        words2 = set(re.findall(r"\b[a-z]+\b", text2.lower()))
        common = words1 & words2
        only_in_1 = words1 - words2
        only_in_2 = words2 - words1
        return {"success": True, "data": {
            "similarity_ratio": round(ratio, 4),
            "common_words": len(common),
            "unique_to_text1": len(only_in_1),
            "unique_to_text2": len(only_in_2)
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_libraries() -> Dict[str, Any]:
    return {"success": True, "data": {"textblob": HAS_TEXTBLOB, "nltk": HAS_NLTK}, "error": None}
