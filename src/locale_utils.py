
import pycountry


def get_countries() -> dict:
    """
    Returns a dictionary of all valid countries with country name as key
    and ISO 3166-1 alpha-2 code as value.
    """
    return {
        country.name: country.alpha_2 for country in pycountry.countries
    }


def get_languages() -> dict:
    """
    Returns a dictionary of valid languages with full name as key
    and ISO 639-1 language code as value. Only includes languages with alpha_2 codes.
    """
    return {
        lang.name: lang.alpha_2
        for lang in pycountry.languages
        if hasattr(lang, 'alpha_2')
    }


def get_country_code(country_name: str) -> str:
    """
    Returns the ISO 3166-1 alpha-2 country code for the given full country name.
    Example: "Germany" -> "DE"
    """

    country = pycountry.countries.get(name=country_name)
    if country:
        return country.alpha_2

    # Try partial or common name matches
    for c in pycountry.countries:
        if country_name.lower() in c.name.lower() or country_name.lower() in getattr(c, 'common_name', '').lower():
            return c.alpha_2

    return None


def get_language_code(language_name: str) -> str:
    """
    Returns the ISO 639-1 code for the given language name.
    Example: "French" -> "fr"
    """

    language_name = language_name.lower()

    for lang in pycountry.languages:
        if hasattr(lang, 'alpha_2') and (
            lang.name.lower() == language_name or language_name in lang.name.lower()):
            return lang.alpha_2

    return None
