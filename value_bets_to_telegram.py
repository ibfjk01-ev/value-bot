import requests
from typing import Any, Dict, List, Optional

API_KEY = "45ccde3fcd3defc883226b1b230bcdb6eada5a4ae796717791796aaea2aa1e47"
BOT_TOKEN = "8693511806:AAEHyiVYNhEki0C1crRdC-4eIcN4-gG9RWM"
CHAT_ID = "253296226"

BASE_URL = "https://api.odds-api.io/v3"

VALUE_BOOKMAKER = "Bet365"
REFERENCE_BOOKMAKER = "Betfair Exchange"

ALLOWED_SPORTS = {"football", "tennis", "basketball"}
ALLOWED_LEAGUES = set()  # leer = alle Ligen

DIFF_THRESHOLD = 0.08
MAX_ALERTS = 10


def send_telegram(message: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        data={"chat_id": CHAT_ID, "text": message},
        timeout=20,
    )
    print("Telegram Status:", response.status_code)


def get_value_bets() -> Any:
    url = f"{BASE_URL}/value-bets"
    params = {
        "apiKey": API_KEY,
        "bookmaker": VALUE_BOOKMAKER,
        "includeEventDetails": "true",
    }
    response = requests.get(url, params=params, timeout=20)
    print("Value Bets Status:", response.status_code)
    response.raise_for_status()
    return response.json()


def get_event_odds(event_id: Any) -> Dict[str, Any]:
    url = f"{BASE_URL}/odds"
    params = {
        "apiKey": API_KEY,
        "eventId": event_id,
        "bookmakers": REFERENCE_BOOKMAKER,
    }
    response = requests.get(url, params=params, timeout=20)
    print(f"Odds Status für {event_id}:", response.status_code)
    response.raise_for_status()
    data = response.json()

    if isinstance(data, list):
        return data[0] if data and isinstance(data[0], dict) else {}
    if isinstance(data, dict):
        return data
    return {}


def normalize_value_bets(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        inner = data.get("data", [])
        if isinstance(inner, list):
            return [x for x in inner if isinstance(x, dict)]
    return []


def get_event_from_bet(bet: Dict[str, Any]) -> Dict[str, Any]:
    event = bet.get("event", {})
    return event if isinstance(event, dict) else {}


def get_event_id_from_bet(bet: Dict[str, Any]) -> Optional[Any]:
    event_id = bet.get("eventId")
    if event_id is not None:
        return event_id

    event = get_event_from_bet(bet)
    return event.get("id")


def normalize_sport(raw: Any) -> str:
    s = str(raw).strip().lower()
    mapping = {
        "football": "football",
        "soccer": "football",
        "tennis": "tennis",
        "basketball": "basketball",
    }
    return mapping.get(s, s)


def get_sport_from_bet(bet: Dict[str, Any]) -> str:
    event = get_event_from_bet(bet)
    sport = event.get("sport", {})

    if isinstance(sport, dict):
        slug = sport.get("slug")
        name = sport.get("name")
        if slug:
            return normalize_sport(slug)
        if name:
            return normalize_sport(name)

    if isinstance(sport, str):
        return normalize_sport(sport)

    top_sport = bet.get("sport")
    if isinstance(top_sport, dict):
        if top_sport.get("slug"):
            return normalize_sport(top_sport.get("slug"))
        if top_sport.get("name"):
            return normalize_sport(top_sport.get("name"))
    if isinstance(top_sport, str):
        return normalize_sport(top_sport)

    return ""


def get_league_slug_from_bet(bet: Dict[str, Any]) -> str:
    event = get_event_from_bet(bet)
    league = event.get("league", {})
    if isinstance(league, dict):
        return str(league.get("slug", "")).strip().lower()
    return ""


def get_market_name_from_bet(bet: Dict[str, Any]) -> str:
    market = bet.get("market", {})
    if isinstance(market, dict):
        name = market.get("name")
        if name:
            return str(name).strip().lower()

    if bet.get("marketName"):
        return str(bet.get("marketName")).strip().lower()

    return ""


def allowed_market(name: str) -> bool:
    n = str(name).strip().lower()

    allowed = {
        "ml",
        "moneyline",
        "h2h",
        "winner",
        "match winner",
        "1x2",
    }

    return n in allowed

def filter_bets(bets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []

    for bet in bets:
        sport = get_sport_from_bet(bet)
        league_slug = get_league_slug_from_bet(bet)
        market = get_market_name_from_bet(bet)

        if ALLOWED_SPORTS and sport not in ALLOWED_SPORTS:
            continue

        if ALLOWED_LEAGUES and league_slug not in ALLOWED_LEAGUES:
            continue

        if not allowed_market(market):
            continue

        result.append(bet)

    return result


def normalize_bookmaker_name(name: str) -> str:
    n = str(name).strip().lower()
    if n in {"betfair exchange", "betfair", "betfair_exchange"}:
        return "Betfair Exchange"
    return name


def parse_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_side_key(raw_key: str) -> str:
    k = str(raw_key).strip().lower()
    mapping = {
        "home": "home",
        "1": "home",
        "away": "away",
        "2": "away",
        "draw": "draw",
        "x": "draw",
        "over": "over",
        "under": "under",
        "yes": "yes",
        "no": "no",
    }
    return mapping.get(k, k)


def parse_odds_mapping(odds_mapping: Dict[str, Any]) -> Dict[str, float]:
    result = {}
    for outcome, price in odds_mapping.items():
        parsed = parse_float(price)
        if parsed is not None:
            result[normalize_side_key(str(outcome))] = parsed
    return result


def extract_first_betfair_odds(odds_data: Dict[str, Any]) -> Dict[str, float]:
    bookmakers = odds_data.get("bookmakers", {})
    if not isinstance(bookmakers, dict):
        return {}

    for raw_name, data in bookmakers.items():
        if normalize_bookmaker_name(raw_name) != "Betfair Exchange":
            continue

        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                odds = item.get("odds")
                if isinstance(odds, dict):
                    parsed = parse_odds_mapping(odds)
                    if parsed:
                        return parsed
                if isinstance(odds, list):
                    for entry in odds:
                        if isinstance(entry, dict):
                            parsed = parse_odds_mapping(entry)
                            if parsed:
                                return parsed

        if isinstance(data, dict):
            direct_odds = data.get("odds")
            if isinstance(direct_odds, dict):
                parsed = parse_odds_mapping(direct_odds)
                if parsed:
                    return parsed
            if isinstance(direct_odds, list):
                for entry in direct_odds:
                    if isinstance(entry, dict):
                        parsed = parse_odds_mapping(entry)
                        if parsed:
                            return parsed

            markets = data.get("markets", {})
            if isinstance(markets, dict):
                for _, market_value in markets.items():
                    if not isinstance(market_value, dict):
                        continue
                    odds = market_value.get("odds")
                    if isinstance(odds, dict):
                        parsed = parse_odds_mapping(odds)
                        if parsed:
                            return parsed
                    if isinstance(odds, list):
                        for entry in odds:
                            if isinstance(entry, dict):
                                parsed = parse_odds_mapping(entry)
                                if parsed:
                                    return parsed

    return {}


def get_side_from_bet(bet: Dict[str, Any]) -> str:
    return str(bet.get("betSide", "")).strip().lower()


def get_price_from_bet(bet: Dict[str, Any]) -> Optional[float]:
    bookmaker_odds = bet.get("bookmakerOdds", {})
    side = get_side_from_bet(bet)

    if not isinstance(bookmaker_odds, dict) or not side:
        return None

    value = bookmaker_odds.get(side)
    if value is None:
        value = bookmaker_odds.get(side.lower())

    return parse_float(value)


def get_ev_display(bet: Dict[str, Any]) -> str:
    ev = bet.get("expectedValue")
    if ev is None:
        return "n/a"

    try:
        ev_float = float(ev)
        if ev_float > 20:
            return f"+{ev_float - 100:.2f}%"
        return f"+{ev_float:.2f}%"
    except (TypeError, ValueError):
        return str(ev)


def build_message(bet: Dict[str, Any], betfair_odds: Dict[str, float]) -> Optional[str]:
    event = get_event_from_bet(bet)

    home = (
        event.get("home")
        or event.get("home_team")
        or event.get("player1")
        or "Home"
    )
    away = (
        event.get("away")
        or event.get("away_team")
        or event.get("player2")
        or "Away"
    )

    sport = get_sport_from_bet(bet) or "unbekannt"
    league = event.get("league", {})
    if isinstance(league, dict):
        league_name = league.get("name") or league.get("slug") or "Unbekannte Liga"
    else:
        league_name = "Unbekannte Liga"

    market = get_market_name_from_bet(bet)
    side = get_side_from_bet(bet)
    price = get_price_from_bet(bet)
    ev_display = get_ev_display(bet)

    display_side = side

    if "team total" in market:
        if side == "home":
            display_side = "over"
        elif side == "away":
            display_side = "under"
    elif "btts" in market or "both teams to score" in market:
        if side == "home":
            display_side = "yes"
        elif side == "away":
            display_side = "no"
    elif "total" in market:
        if side == "home":
            display_side = "over"
        elif side == "away":
            display_side = "under"

    bf_price = None
    if isinstance(betfair_odds, dict):
        bf_price = betfair_odds.get(side)
        if bf_price is None:
            bf_price = betfair_odds.get(normalize_side_key(side))

    bf_price = parse_float(bf_price)

    if price is not None and bf_price is not None:
        diff = price - bf_price

        if diff <= 0:
            return None

        if diff > DIFF_THRESHOLD:
            header = "🟢 STRONG VALUE"
            verdict = f"Value ueber Betfair: +{diff:.2f}"
        else:
            header = "🔵 SMALL VALUE"
            verdict = "Kleiner Value gegenueber Markt"
    else:
        return None

    return f"""Sport: {sport}
Event: {home} vs {away}
Liga: {league_name}
Market: {market}
Side: {display_side}

Bet365: {price}
Betfair: {bf_price}
EV: {ev_display}

{verdict}
"""




def main() -> None:
    print("MAIN START")

    data = get_value_bets()
    bets = normalize_value_bets(data)
    print("Total Bets:", len(bets))

    bets = filter_bets(bets)
    print("After Filter:", len(bets))

    if not bets:
        send_telegram("Keine passenden Value Bets gefunden.")
        return

    sent = 0

    for bet in bets:
        event_id = get_event_id_from_bet(bet)
        if not event_id:
            continue

        try:
            odds_data = get_event_odds(event_id)
            betfair_odds = extract_first_betfair_odds(odds_data)
            message = build_message(bet, betfair_odds)

            if message is None:
                continue

            send_telegram(message)
            sent += 1

            if sent >= MAX_ALERTS:
                break

        except Exception as e:
            print(f"Fehler bei Event {event_id}: {e}")

    print("Gesendet:", sent)


if __name__ == "__main__":
    main()
