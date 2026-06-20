from flask import Flask, jsonify, request, g
from flask_cors import CORS
from nepse_data_api import Nepse

app = Flask(__name__)
CORS(app)


def get_nepse():
    if "nepse" not in g:
        g.nepse = Nepse(enable_cache=False)
        g.nepse.authenticate()
    return g.nepse


@app.teardown_appcontext
def teardown(exception=None):
    g.pop("nepse", None)




@app.route("/api/symbols")
def get_symbols():
    try:
        stocks = get_nepse().get_stocks()
        symbols = sorted(set(s["symbol"] for s in stocks))
        return jsonify({"symbols": symbols, "count": len(symbols)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stock/<symbol>")
def get_stock_info(symbol):
    try:
        symbol = symbol.upper()
        companies = get_nepse().get_company_list()
        match = next((c for c in companies if c["symbol"] == symbol), None)
        if not match:
            return jsonify({"error": f"Symbol {symbol} not found"}), 404

        security_id = match["id"]
        details = get_nepse().get_security_details(security_id)
        trade = details.get("securityDailyTradeDto", {})

        stocks = get_nepse().get_stocks()
        current = next((s for s in stocks if s["symbol"] == symbol), None)

        ltp = trade.get("lastTradedPrice", 0) or 0
        prev_close = trade.get("previousClose", 0) or 0
        volume = trade.get("totalTradeQuantity", 0) or 0
        turnover = current.get("totalTradeValue", 0) if current else 0
        vwap = round(turnover / volume, 2) if volume > 0 else 0

        return jsonify({
            "symbol": symbol,
            "securityName": details.get("security", {}).get("securityName", ""),
            "ltp": ltp,
            "pointChange": round(ltp - prev_close, 2),
            "percentChange": current.get("percentageChange", 0) if current else 0,
            "open": trade.get("openPrice", 0) or 0,
            "high": trade.get("highPrice", 0) or 0,
            "low": trade.get("lowPrice", 0) or 0,
            "close": trade.get("closePrice", 0) or 0,
            "vwap": vwap,
            "volume": volume,
            "turnover": turnover,
            "previousClose": prev_close,
            "fiftyTwoWeekHigh": trade.get("fiftyTwoWeekHigh"),
            "fiftyTwoWeekLow": trade.get("fiftyTwoWeekLow"),
            "lastUpdatedDateTime": trade.get("lastUpdatedDateTime", ""),
            "businessDate": trade.get("businessDate", "")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stock/<symbol>/history")
def get_stock_history(symbol):
    try:
        symbol = symbol.upper()
        period = request.args.get("period", "1w")

        companies = get_nepse().get_company_list()
        match = next((c for c in companies if c["symbol"] == symbol), None)
        if not match:
            return jsonify({"error": f"Symbol {symbol} not found"}), 404

        from datetime import datetime, timedelta
        end = datetime.now()
        days = {"1d": 1, "5d": 5, "1w": 7, "2w": 14, "1m": 30, "3m": 90, "6m": 180, "1y": 365}
        start = end - timedelta(days=days.get(period, 7))

        hist = get_nepse().get_historical_chart(
            match["id"],
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d")
        )
        return jsonify(hist if isinstance(hist, list) else [])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/market")
def get_market_data():
    try:
        stocks = get_nepse().get_stocks()
        result = []
        for s in stocks:
            ltp = s.get("lastTradedPrice", 0) or 0
            prev_close = s.get("previousClose", 0) or 0
            result.append({
                "symbol": s["symbol"],
                "securityName": s.get("securityName", ""),
                "ltp": ltp,
                "pointChange": round(ltp - prev_close, 2),
                "percentChange": s.get("percentageChange", 0),
                "open": s.get("openPrice", 0) or 0,
                "high": s.get("highPrice", 0) or 0,
                "low": s.get("lowPrice", 0) or 0,
                "volume": s.get("totalTradeQuantity", 0) or 0,
                "turnover": s.get("totalTradeValue", 0) or 0,
                "previousClose": prev_close,
                "lastUpdatedDateTime": s.get("lastUpdatedDateTime", "")
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/index")
def get_market_index():
    try:
        indices = get_nepse().get_nepse_index()
        summary = get_nepse().get_market_summary()
        gainers = get_nepse().get_top_gainers(limit=5)
        losers = get_nepse().get_top_losers(limit=5)
        market_status = get_nepse().get_market_status()

        def find_index(name):
            return next((i for i in indices if i.get("index") == name), {})

        summary_dict = {}
        for item in summary:
            key = item["detail"].replace(":", "").replace(" ", "_").lower().replace("rs:", "")
            summary_dict[key] = item["value"]

        return jsonify({
            "nepse_index": find_index("NEPSE Index"),
            "sensitive_index": find_index("Sensitive Index"),
            "float_index": find_index("Float Index"),
            "market_summary": summary_dict,
            "top_gainers": gainers,
            "top_losers": losers,
            "market_status": market_status
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sub-indices")
def get_sub_indices():
    try:
        return jsonify(get_nepse().get_sub_indices())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/")
def index():
    return jsonify({
        "name": "NEPSE API",
        "version": "2.0",
        "source": "nepalstock.com.np (via nepse-data-api)",
        "endpoints": {
            "/api/symbols": "List all available symbols",
            "/api/stock/<symbol>": "Get current info for a stock",
            "/api/stock/<symbol>/history?period=1w": "Get historical data",
            "/api/market": "Get all stocks with OHLCV data",
            "/api/index": "Get NEPSE index, market summary, top gainers/losers",
            "/api/sub-indices": "Get sector indices"
        }
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
