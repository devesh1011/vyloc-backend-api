"""
Prompt templates for Vyloc localization.

These prompts are designed to be modular and handle:
1. Text translation while preserving design layout
2. Cultural adaptation of visual elements (models, colors, symbols)
3. Demographic-appropriate representation
"""

from typing import Optional
from app.schemas.localization import TargetLanguage, TargetMarket


# Language to native name mapping for better prompt accuracy
LANGUAGE_NATIVE_NAMES = {
    TargetLanguage.HINDI: "हिंदी (Hindi)",
    TargetLanguage.JAPANESE: "日本語 (Japanese)",
    TargetLanguage.KOREAN: "한국어 (Korean)",
    TargetLanguage.GERMAN: "Deutsch (German)",
    TargetLanguage.FRENCH: "Français (French)",
    TargetLanguage.SPANISH: "Español (Spanish)",
    TargetLanguage.ITALIAN: "Italiano (Italian)",
    TargetLanguage.PORTUGUESE: "Português (Portuguese)",
    TargetLanguage.CHINESE_SIMPLIFIED: "简体中文 (Simplified Chinese)",
    TargetLanguage.CHINESE_TRADITIONAL: "繁體中文 (Traditional Chinese)",
    TargetLanguage.ARABIC: "العربية (Arabic)",
    TargetLanguage.RUSSIAN: "Русский (Russian)",
    TargetLanguage.THAI: "ไทย (Thai)",
    TargetLanguage.VIETNAMESE: "Tiếng Việt (Vietnamese)",
    TargetLanguage.INDONESIAN: "Bahasa Indonesia (Indonesian)",
}

# Market to demographic description mapping
MARKET_DEMOGRAPHICS = {
    TargetMarket.INDIA: {
        "ethnicity": "South Asian/Indian",
        "cultural_notes": "Use warm, vibrant colors. Family-oriented messaging resonates well.",
        "avoid": "beef imagery, overtly western symbols"
    },
    TargetMarket.JAPAN: {
        "ethnicity": "Japanese/East Asian",
        "cultural_notes": "Clean, minimalist design. Quality and precision are valued.",
        "avoid": "number 4 (shi=death), white flowers (funerals)"
    },
    TargetMarket.SOUTH_KOREA: {
        "ethnicity": "Korean/East Asian",
        "cultural_notes": "K-beauty aesthetics, youthful appearance, trendy style.",
        "avoid": "red ink for names, number 4"
    },
    TargetMarket.GERMANY: {
        "ethnicity": "European/German",
        "cultural_notes": "Direct, factual messaging. Quality and engineering excellence valued.",
        "avoid": "aggressive sales tactics, exaggeration"
    },
    TargetMarket.FRANCE: {
        "ethnicity": "European/French",
        "cultural_notes": "Elegant, sophisticated aesthetics. Art and culture appreciated.",
        "avoid": "overly casual tone, aggressive marketing"
    },
    TargetMarket.SPAIN: {
        "ethnicity": "European/Spanish",
        "cultural_notes": "Warm, family-oriented. Bold colors work well.",
        "avoid": "purple (associated with death in some contexts)"
    },
    TargetMarket.ITALY: {
        "ethnicity": "European/Italian",
        "cultural_notes": "Style, fashion, and craftsmanship are valued.",
        "avoid": "overly casual approach to quality claims"
    },
    TargetMarket.BRAZIL: {
        "ethnicity": "Brazilian (diverse, mixed heritage)",
        "cultural_notes": "Vibrant, joyful imagery. Family and community valued.",
        "avoid": "purple and black together (mourning)"
    },
    TargetMarket.CHINA: {
        "ethnicity": "Chinese/East Asian",
        "cultural_notes": "Red is lucky. Gold represents prosperity.",
        "avoid": "number 4, white/black (funerals), clock imagery"
    },
    TargetMarket.TAIWAN: {
        "ethnicity": "Taiwanese/East Asian",
        "cultural_notes": "Similar to mainland but more traditional in some aspects.",
        "avoid": "political sensitivities, number 4"
    },
    TargetMarket.MIDDLE_EAST: {
        "ethnicity": "Middle Eastern/Arab",
        "cultural_notes": "Modest dress codes. Green is positive. Family values.",
        "avoid": "revealing clothing, pork imagery, left-hand gestures"
    },
    TargetMarket.RUSSIA: {
        "ethnicity": "Russian/Eastern European",
        "cultural_notes": "Direct messaging. Quality and durability valued.",
        "avoid": "yellow flowers (infidelity), even numbers of flowers"
    },
    TargetMarket.THAILAND: {
        "ethnicity": "Thai/Southeast Asian",
        "cultural_notes": "Respect for monarchy and Buddhism. Politeness valued.",
        "avoid": "feet/soles shown, head touching, Buddha imagery in ads"
    },
    TargetMarket.VIETNAM: {
        "ethnicity": "Vietnamese/Southeast Asian",
        "cultural_notes": "Family-oriented. Red and yellow are positive colors.",
        "avoid": "three in photographs (superstition)"
    },
    TargetMarket.INDONESIA: {
        "ethnicity": "Indonesian/Southeast Asian",
        "cultural_notes": "Diverse, multicultural. Modest dress appropriate.",
        "avoid": "left-hand gestures, pork imagery"
    },
    TargetMarket.USA: {
        "ethnicity": "American (diverse)",
        "cultural_notes": "Direct, benefit-focused messaging. Diversity appreciated.",
        "avoid": "culturally insensitive stereotypes"
    },
    TargetMarket.UK: {
        "ethnicity": "British (diverse)",
        "cultural_notes": "Understated, witty messaging. Quality valued.",
        "avoid": "overly aggressive sales tactics"
    },
}

# Default market mapping from language
LANGUAGE_TO_DEFAULT_MARKET = {
    TargetLanguage.HINDI: TargetMarket.INDIA,
    TargetLanguage.JAPANESE: TargetMarket.JAPAN,
    TargetLanguage.KOREAN: TargetMarket.SOUTH_KOREA,
    TargetLanguage.GERMAN: TargetMarket.GERMANY,
    TargetLanguage.FRENCH: TargetMarket.FRANCE,
    TargetLanguage.SPANISH: TargetMarket.SPAIN,
    TargetLanguage.ITALIAN: TargetMarket.ITALY,
    TargetLanguage.PORTUGUESE: TargetMarket.BRAZIL,
    TargetLanguage.CHINESE_SIMPLIFIED: TargetMarket.CHINA,
    TargetLanguage.CHINESE_TRADITIONAL: TargetMarket.TAIWAN,
    TargetLanguage.ARABIC: TargetMarket.MIDDLE_EAST,
    TargetLanguage.RUSSIAN: TargetMarket.RUSSIA,
    TargetLanguage.THAI: TargetMarket.THAILAND,
    TargetLanguage.VIETNAMESE: TargetMarket.VIETNAM,
    TargetLanguage.INDONESIAN: TargetMarket.INDONESIA,
}


def build_localization_prompt(
    target_language: TargetLanguage,
    target_market: Optional[TargetMarket] = None,
    source_language: str = "english",
    preserve_faces: bool = False,
) -> str:
    """
    Build a comprehensive localization prompt for Gemini Imagen optimized for Nano Banana.
    
    This prompt follows Google's best practices:
    - Structured with Subject, Composition, Action, Location, Style
    - Specific camera and lighting controls
    - Direct editing instructions for text translation
    - Studio-quality output specifications
    
    Args:
        target_language: The language to translate text into
        target_market: The market for cultural adaptation (inferred from language if not provided)
        source_language: The source language of the original image
        preserve_faces: If True, keep original faces; if False, adapt to target demographics
        
    Returns:
        A comprehensive prompt string optimized for Gemini Imagen
    """
    # Get native language name
    native_name = LANGUAGE_NATIVE_NAMES.get(target_language, target_language.value.title())
    
    # Infer market from language if not provided
    if target_market is None:
        target_market = LANGUAGE_TO_DEFAULT_MARKET.get(target_language)
    
    # Get market demographics
    demographics = MARKET_DEMOGRAPHICS.get(target_market) if target_market else {}
    if demographics is None:
        demographics = {}
    ethnicity = demographics.get("ethnicity", "appropriate local")
    cultural_notes = demographics.get("cultural_notes", "")
    avoid = demographics.get("avoid", "")
    
    market_name = target_market.value.replace('_', ' ').title() if target_market else 'international'
    
    # Build the prompt following Google's Nano Banana structure
    prompt_parts = [
        # OBJECTIVE - Clear transformation goal
        f"Transform this advertisement image into a {market_name} market-ready version with localized text in {native_name}.",
        "",
        # EDITING INSTRUCTIONS - Direct, specific commands (most important for image editing)
        "## EDITING INSTRUCTIONS",
        f"1. TEXT TRANSLATION: Translate ALL visible text from {source_language.title()} to {native_name}",
        f"   - Render text using authentic {target_language.value.replace('_', ' ').title()} typography and script",
        "   - Maintain EXACT placement, size hierarchy, font weight, and visual emphasis of original text",
        "   - Keep brand names and logos in their original form (unless official localized versions exist)",
        "   - Ensure perfect kerning, spacing, and legibility",
        "",
        "2. LAYOUT PRESERVATION: Maintain the original composition EXACTLY",
        "   - Keep identical framing, aspect ratio, and visual hierarchy",
        "   - Preserve all design elements, borders, and decorative components in their exact positions",
        "   - Do not crop, resize, or reframe any element",
        "",
        "3. PRODUCT CONSISTENCY: Keep the product appearance 100% identical",
        "   - Do not modify product shape, color, texture, or any physical attribute",
        "   - Maintain product positioning and scale exactly as shown",
        "   - Preserve all product details, reflections, and material properties",
        "",
    ]
    
    # Add people/demographic adaptation
    if not preserve_faces:
        prompt_parts.extend([
            f"4. DEMOGRAPHIC LOCALIZATION: Adapt people/models to {ethnicity} appearance",
            "   - Maintain identical poses, expressions, gestures, and body language",
            "   - Keep clothing style similar but ensure cultural appropriateness",
            "   - Preserve the same age range, gender presentation, and styling aesthetic",
            "   - Match the original mood, energy, and emotional tone",
            "",
        ])
    else:
        prompt_parts.extend([
            "4. PEOPLE PRESERVATION: Keep all people/models exactly as they appear",
            "   - Do not modify faces, skin tone, features, or styling of any person",
            "   - Maintain original demographics and appearance completely",
            "",
        ])
    
    # STYLE & TECHNICAL SPECIFICATIONS - Professional quality controls
    prompt_parts.extend([
        "## STYLE & TECHNICAL SPECIFICATIONS",
        "- Style: Photorealistic professional product photography/advertisement",
        "- Format: Match original aspect ratio and dimensions precisely",
        "- Quality: Studio-grade commercial advertising quality",
        "",
        "## CAMERA & LIGHTING",
        "- Maintain the original camera angle, perspective, and depth of field",
        "- Preserve existing lighting setup (key light, fill light, rim light positions)",
        "- Match original color grading, contrast, and tonal range",
        "- Keep identical shadows, highlights, and ambient lighting",
        "- Maintain original white balance and color temperature",
        "",
    ])
    
    # Cultural adaptation
    if cultural_notes or avoid:
        prompt_parts.extend([
            "## CULTURAL ADAPTATION",
        ])
        if cultural_notes:
            prompt_parts.append(f"- Cultural context: {cultural_notes}")
        if avoid:
            prompt_parts.append(f"- Cultural sensitivity: Avoid {avoid}")
        prompt_parts.append("")
    
    # Output quality requirements
    prompt_parts.extend([
        "## OUTPUT REQUIREMENTS",
        "- Photorealistic, professional commercial advertising quality",
        "- Zero artifacts, distortions, or generative AI tell-tale signs",
        "- Crisp, razor-sharp text rendering with perfect legibility",
        "- Seamless integration of all localized elements",
        "- Natural, believable result that looks like an original advertisement",
        "- Match or exceed the technical quality of the input image",
    ])
    
    return "\n".join(prompt_parts)


def build_watermark_removal_prompt() -> str:
    """
    Build a prompt for watermark removal using Gemini conversational editing.
    
    Returns:
        A prompt string for removing watermarks
    """
    return """Remove any watermarks, logos, or text overlays that appear to be added by AI generation tools.
    
Specifically:
- Remove any "Gemini" branding or logos
- Remove any watermarks in corners or edges
- Remove any "Made with AI" or similar text
- Preserve ALL original content and product elements

The image should look like a clean, professional advertisement with no AI generation artifacts visible."""
