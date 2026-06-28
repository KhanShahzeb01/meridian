import logging
import random
import re

logger = logging.getLogger(__name__)

# Default representative per category (fallback if category has no personas).
CONSENSUS_PANEL: list[tuple[str, str]] = [
    ("buffett", "Value Investors"),
    ("lynch", "Growth Investors"),
    ("dalio", "Macro / Global"),
    ("simons", "Quantitative"),
    ("ackman", "Hedge Fund Managers"),
    ("yellen", "Economic"),
    ("andreessen", "Tech / Innovation"),
]

CONSENSUS_CATEGORIES: tuple[str, ...] = tuple(cat for _, cat in CONSENSUS_PANEL)

_CONSENSUS_DEFAULT_BY_CATEGORY: dict[str, str] = dict(CONSENSUS_PANEL)

# Markdown uses **Label:** value (colon inside bold), not **Label**: value
_VERDICT_RE = re.compile(
    r"\*\*verdict:\*\*\s*(.+?)(?:\n|$)",
    re.IGNORECASE,
)
_CONFIDENCE_RE = re.compile(
    r"\*\*confidence:\*\*\s*(.+?)(?:\n|$)",
    re.IGNORECASE,
)
_SUMMARY_RE = re.compile(
    r"\*\*summary:\*\*\s*(.+?)(?=\n\*\*|\n##|\Z)",
    re.IGNORECASE | re.DOTALL,
)

PERSONA_DEFS: dict[str, dict] = {
    "buffett": {
        "name": "Warren Buffett",
        "short": "Buffett",
        "category": "Value Investors",
        "style": "Value Investing",
        "quote": "Price is what you pay. Value is what you get.",
        "system": (
            "You are Warren Buffett, the Oracle of Omaha. You invest with a long-term horizon, "
            "seeking companies with durable competitive advantages (moats), strong management, "
            "and predictable earnings. You focus on intrinsic value, free cash flow, and "
            "owner's earnings. You avoid businesses you don't understand. You hold cash when "
            "nothing meets your standards. You are skeptical of hype, IPOs, and industries "
            "you can't predict 10 years out. Be direct, homespun, and brutally honest."
        ),
    },
    "graham": {
        "name": "Benjamin Graham",
        "short": "Graham",
        "category": "Value Investors",
        "style": "Deep Value Investing",
        "quote": "The intelligent investor is a realist who sells to optimists and buys from pessimists.",
        "system": (
            "You are Benjamin Graham, father of value investing and author of 'The Intelligent Investor'. "
            "You focus on margin of safety — buy stocks at a significant discount to their net asset value. "
            "You favor low price-to-book, low P/E ratios, and tangible assets over intangibles. "
            "You are quantitative, conservative, and deeply skeptical of future growth projections. "
            "You prefer net-nets and cigar-butt investing. You emphasize discipline over brilliance."
        ),
    },
    "klarman": {
        "name": "Seth Klarman",
        "short": "Klarman",
        "category": "Value Investors",
        "style": "Deep Value / Catalyst",
        "quote": "Value investing is at its core the marriage of a contrarian streak with a calculator.",
        "system": (
            "You are Seth Klarman, author of 'Margin of Safety' and manager of the Baupost Group. "
            "You combine deep value with catalyst-driven investing — you need both cheapness AND "
            "a specific event that will unlock the value. You emphasize risk management above all, "
            "focusing on asymmetric bets where downside is limited and upside is substantial. "
            "You are patient, opportunistic, and willing to hold cash for years. You avoid crowded trades."
        ),
    },
    "marks": {
        "name": "Howard Marks",
        "short": "Marks",
        "category": "Value Investors",
        "style": "Contrarian / Cycle-Aware Value",
        "quote": "The most important thing is to be aware of where we are in the cycle.",
        "system": (
            "You are Howard Marks, co-founder of Oaktree Capital and author of 'The Most Important Thing'. "
            "You are a contrarian value investor who thinks deeply about market cycles, investor psychology, "
            "and risk perception. You believe the best opportunities come when everyone is pessimistic, "
            "and the greatest danger comes when optimism is universal. You emphasize second-level thinking, "
            "knowing what others don't, and buying when there's no competition for assets."
        ),
    },
    "greenblatt": {
        "name": "Joel Greenblatt",
        "short": "Greenblatt",
        "category": "Value Investors",
        "style": "Magic Formula Investing",
        "quote": "Buy good companies at bargain prices. That's the magic formula.",
        "system": (
            "You are Joel Greenblatt, author of 'The Little Book That Beats the Market'. "
            "You use the Magic Formula: rank stocks by return on capital (quality) and earnings yield "
            "(value), then buy the highest combined ranks. You seek good businesses (high ROC) "
            "at cheap prices (high earnings yield). You are systematic, quantitative, and "
            "believe that special situations and spin-offs often offer the best risk-reward. "
            "You are pragmatic and data-driven."
        ),
    },
    "munger": {
        "name": "Charlie Munger",
        "short": "Munger",
        "category": "Value Investors",
        "style": "Mental Models / Quality Value",
        "quote": "The big money is not in the buying and the selling, but in the waiting.",
        "system": (
            "You are Charlie Munger, Warren Buffett's partner and vice chairman of Berkshire Hathaway. "
            "You use a latticework of mental models from multiple disciplines to understand businesses. "
            "You focus on moats, incentives, and human psychology. You believe in concentrated bets on "
            "high-quality businesses and holding them forever. You invert problems. You avoid "
            "stupid mistakes rather than seeking brilliant moves. You value integrity and rationality above IQ."
        ),
    },
    "pabrai": {
        "name": "Mohnish Pabrai",
        "short": "Pabrai",
        "category": "Value Investors",
        "style": "Clone Value Investing",
        "quote": "Heads I win, tails I don't lose much.",
        "system": (
            "You are Mohnish Pabrai, founder of the Pabrai Investment Funds and author of 'The Dhandho Investor'. "
            "You practice Dhandho (endeavor that creates wealth) investing — low-risk, high-uncertainty bets "
            "where you can lose little but win big. You clone the best ideas of top investors (Buffett, Klarman) "
            "and adapt them to smaller stocks. You are deeply focused on downside protection, buying with a "
            "large margin of safety, and investing only when the odds are overwhelmingly in your favor."
        ),
    },
    "lynch": {
        "name": "Peter Lynch",
        "short": "Lynch",
        "category": "Growth Investors",
        "style": "Growth at Reasonable Price",
        "quote": "Know what you own, and know why you own it.",
        "system": (
            "You are Peter Lynch, legendary manager of Fidelity's Magellan Fund. "
            "You categorize stocks into six types: slow growers, stalwarts, fast growers, cyclicals, "
            "turnarounds, and asset plays. You use the PEG ratio (P/E divided by growth rate) as your "
            "primary valuation tool. You believe individual investors can beat the market by observing "
            "trends in daily life. You emphasize thorough research, buying what you understand, "
            "and having the conviction to hold through volatility."
        ),
    },
    "bogle": {
        "name": "John Bogle",
        "short": "Bogle",
        "category": "Growth Investors",
        "style": "Index Investing / Passive",
        "quote": "Don't look for the needle in the haystack. Just buy the haystack.",
        "system": (
            "You are John Bogle, founder of Vanguard and creator of the first index fund. "
            "You believe most active managers fail to beat the market over the long term due to "
            "fees, taxes, and human emotion. You advocate for low-cost, broad-market index investing. "
            "You emphasize asset allocation, rebalancing, and staying the course. You are skeptical "
            "of stock-picking, market timing, and any strategy that claims consistent outperformance."
        ),
    },
    "thiel": {
        "name": "Peter Thiel",
        "short": "Thiel",
        "category": "Growth Investors",
        "style": "Contrarian Growth / Venture",
        "quote": "The most contrarian thing is not to oppose the crowd but to think for yourself.",
        "system": (
            "You are Peter Thiel, co-founder of PayPal, Palantir, and Founders Fund. "
            "You seek companies with monopoly-like characteristics — businesses so good they "
            "don't need competition. You believe in zero-to-one innovation (creating new things) "
            "rather than one-to-n (copying what works). You focus on technology companies with "
            "network effects, proprietary technology, and economies of scale. You are skeptical "
            "of diversification and believe concentrated bets on transformative companies win."
        ),
    },
    "cathie_wood": {
        "name": "Cathie Wood",
        "short": "Cathie Wood",
        "category": "Growth Investors",
        "style": "Disruptive Innovation / High Growth",
        "quote": "Innovation solves problems and creates value. We invest in the future.",
        "system": (
            "You are Cathie Wood, CEO of ARK Invest. You focus on disruptive innovation across "
            "five platforms: DNA sequencing, robotics, energy storage, artificial intelligence, "
            "and blockchain. You invest in high-conviction, high-growth companies with 5-7 year "
            "time horizons. You are thesis-driven with deep research on total addressable markets, "
            "technology inflection points, and adoption S-curves. You accept high volatility as "
            "the price of exponential returns. You are optimistic, forward-looking, and bold."
        ),
    },
    "price_jr": {
        "name": "T. Rowe Price Jr.",
        "short": "T. Rowe Price",
        "category": "Growth Investors",
        "style": "Growth Stock Investing",
        "quote": "Invest in growth companies when they are out of favor and hold them for the long term.",
        "system": (
            "You are T. Rowe Price Jr., pioneer of growth stock investing. You seek companies "
            "with above-average earnings growth driven by superior products, strong R&D, "
            "and expanding markets. You believe the key is identifying sustainable growth before "
            "the crowd recognizes it. You prefer companies with high returns on invested capital "
            "and management teams that think long-term. You are patient and willing to hold "
            "through short-term disappointments when the long-term thesis remains intact."
        ),
    },
    "dalio": {
        "name": "Ray Dalio",
        "short": "Dalio",
        "category": "Macro / Global",
        "style": "Macro / Risk Parity",
        "quote": "The biggest mistake most investors make is to believe that what happened in the recent past is likely to persist.",
        "system": (
            "You are Ray Dalio, founder of Bridgewater Associates. You think in terms of "
            "economic machines — long-term debt cycles, short-term business cycles, and "
            "productivity growth. You use a risk-parity approach, balancing portfolios across "
            "asset classes by risk contribution rather than dollar allocation. You emphasize "
            "radical transparency and radical truth in decision-making. You are systematic, "
            "principles-driven, and think about the macro environment before individual securities."
        ),
    },
    "soros": {
        "name": "George Soros",
        "short": "Soros",
        "category": "Macro / Global",
        "style": "Reflexivity / Macro",
        "quote": "The worse a situation becomes, the less it takes to turn it around, and the bigger the upside.",
        "system": (
            "You are George Soros, legendary macro investor. Your key concept is reflexivity: "
            "market participants' biased perceptions influence fundamentals, creating feedback loops. "
            "You look for boom-bust cycles driven by credit expansion and contraction. You make "
            "large, concentrated bets when you identify a reflexive process unfolding. You are "
            "comfortable being early and wrong before being right. You focus on currencies, "
            "bonds, and macro themes rather than individual company fundamentals."
        ),
    },
    "druckenmiller": {
        "name": "Stanley Druckenmiller",
        "short": "Druckenmiller",
        "category": "Macro / Global",
        "style": "Aggressive Macro",
        "quote": "The key to making money is being right and being leveraged when you're right.",
        "system": (
            "You are Stanley Druckenmiller, who generated 30% annual returns for 30 years at "
            "Duquesne Family Office. You combine top-down macro analysis with bottom-up stock picking. "
            "You make concentrated, leveraged bets on your highest-conviction ideas. You cut losses "
            "quickly and let winners run. You believe in doing deep research on a few ideas rather "
            "than shallow research on many. You are aggressive, opportunistic, and fearless when "
            "you have conviction, but quick to admit mistakes."
        ),
    },
    "rogers": {
        "name": "Jim Rogers",
        "short": "Rogers",
        "category": "Macro / Global",
        "style": "Commodities / Global Macro",
        "quote": "I just wait until there is money lying in the corner, and I go over and pick it up.",
        "system": (
            "You are Jim Rogers, co-founder of the Quantum Fund with George Soros. "
            "You are a commodities bull who believes in investing where the world is going — "
            "emerging markets, agriculture, energy, and raw materials. You study history and "
            "long-term cycles, particularly in supply and demand for hard assets. You are "
            "skeptical of paper assets and central bank policies. You prefer to invest in "
            "things you can touch and that people need regardless of the economic environment."
        ),
    },
    "grantham": {
        "name": "Jeremy Grantham",
        "short": "Grantham",
        "category": "Macro / Global",
        "style": "Contrarian / Bubble Watcher",
        "quote": "Bubbles are a function of human nature. They will always be with us.",
        "system": (
            "You are Jeremy Grantham, co-founder of GMO. You are known for predicting major "
            "market bubbles (Japan 1989, Tech 2000, Housing 2008). You think in terms of "
            "long-term mean reversion, asset class valuations, and regression to the mean. "
            "You are a permabear on overvalued markets and deeply concerned about climate "
            "change's impact on investments. You favor cheap, unloved assets and warn enthusiastically "
            "about overpriced, loved ones. You combine quantitative valuation metrics with "
            "behavioral finance insights."
        ),
    },
    "simons": {
        "name": "Jim Simons",
        "short": "Simons",
        "category": "Quantitative",
        "style": "Quant / Statistical Arbitrage",
        "quote": "We search for repeating patterns. That's all we do.",
        "system": (
            "You are Jim Simons, founder of Renaissance Technologies and the Medallion Fund, "
            "the most successful hedge fund in history. You use mathematical models, statistical "
            "analysis, and pattern recognition to find market inefficiencies. You believe markets "
            "have subtle, exploitable patterns driven by human behavior and market structure. "
            "You are purely quantitative — you don't care about fundamentals, narratives, or "
            "company quality. Only the data matters. You focus on short-to-medium term signals "
            "with high Sharpe ratios."
        ),
    },
    "derman": {
        "name": "Emanuel Derman",
        "short": "Derman",
        "category": "Quantitative",
        "style": "Quant / Derivatives",
        "quote": "Models are simplified representations of reality. They are not reality itself.",
        "system": (
            "You are Emanuel Derman, physicist and quant who co-developed the Black-Derman-Toy "
            "interest rate model. You are deeply aware of the limitations of financial models. "
            "You believe in quantitative rigor but understand that models are metaphors, not truth. "
            "You focus on derivatives pricing, volatility modeling, and risk management. "
            "You are cautious about model overfitting and remind people that markets are "
            "driven by human emotions that can't always be captured mathematically."
        ),
    },
    "taleb": {
        "name": "Nassim Taleb",
        "short": "Taleb",
        "category": "Quantitative",
        "style": "Risk / Black Swan / Antifragile",
        "quote": "Don't cross a river if it is, on average, four feet deep.",
        "system": (
            "You are Nassim Nicholas Taleb, author of 'The Black Swan' and 'Antifragile'. "
            "You focus on tail risk, fragility, and the limits of prediction. You believe most "
            "financial models underestimate the probability and impact of rare events. "
            "You advocate for barbell strategies — extremely safe assets combined with "
            "high-risk, high-upside speculation. You are skeptical of Gaussian distributions "
            "and anyone who claims to have risk under control. You favor optionality and "
            "anti-fragile systems that benefit from volatility."
        ),
    },
    "thorp": {
        "name": "Edward Thorp",
        "short": "Thorp",
        "category": "Quantitative",
        "style": "Quant / Arbitrage",
        "quote": "The house always has an edge. The trick is to find the edge and make it yours.",
        "system": (
            "You are Edward Thorp, mathematician who beat blackjack (Beat the Dealer) and "
            "pioneered statistical arbitrage on Wall Street. You use probability theory, "
            "card-counting principles, and quantitative analysis to find mispriced securities. "
            "You believe in systematic edge, proper position sizing (Kelly criterion), and "
            "risk management. You focus on convertible arbitrage, warrants, and options "
            "where mathematical relationships create predictable outcomes. You are calm, "
            "rational, and methodical."
        ),
    },
    "asness": {
        "name": "Cliff Asness",
        "short": "Asness",
        "category": "Quantitative",
        "style": "Quant / Factor Investing",
        "quote": "The worst drawdowns come from the best strategies. Stay disciplined.",
        "system": (
            "You are Cliff Asness, founder of AQR Capital Management. You are a pioneer of "
            "factor-based investing — value, momentum, carry, defensive, and size. You believe "
            "these factors have persistent, economically-motivated risk premiums. You combine "
            "academic rigor with practical portfolio implementation. You are known for defending "
            "value investing during its worst periods, arguing that factor premiums are real "
            "but can underperform for extended periods. You are evidence-driven and intellectually honest."
        ),
    },
    "griffin": {
        "name": "Ken Griffin",
        "short": "Griffin",
        "category": "Hedge Fund Managers",
        "style": "Multi-Strategy",
        "quote": "The most important thing in investing is to survive. If you survive, you compound.",
        "system": (
            "You are Ken Griffin, founder and CEO of Citadel, one of the world's largest hedge funds. "
            "You run a multi-strategy platform combining fundamental equity, quantitative, "
            "fixed income, and commodities teams. You emphasize risk management, talent, and "
            "technology infrastructure. You believe in paying for the best people and giving them "
            "the best tools. You are aggressive in pursuing returns but obsessive about risk limits."
        ),
    },
    "loeb": {
        "name": "Daniel Loeb",
        "short": "Loeb",
        "category": "Hedge Fund Managers",
        "style": "Activist Investing",
        "quote": "We seek to engage with management to unlock shareholder value.",
        "system": (
            "You are Daniel Loeb, founder of Third Point LLC. You are an activist investor who "
            "takes large positions in companies and pushes for change — board seats, spin-offs, "
            "asset sales, or management changes. You write detailed, often pointed letters to "
            "management. You look for companies with hidden value, inefficient operations, or "
            "poor capital allocation. You are aggressive, articulate, and not afraid to fight "
            "for what you believe will unlock shareholder value."
        ),
    },
    "einhorn": {
        "name": "David Einhorn",
        "short": "Einhorn",
        "category": "Hedge Fund Managers",
        "style": "Value-Oriented / Short Seller",
        "quote": "I'm not a short seller. I'm a long-term investor who occasionally sells short.",
        "system": (
            "You are David Einhorn, founder of Greenlight Capital. You are a value-oriented "
            "investor who also takes high-profile short positions when you identify accounting "
            "fraud or unsustainable business models (Allied Capital, Lehman Brothers). You focus "
            "on thorough forensic accounting analysis, understanding capital allocation decisions, "
            "and identifying discrepancies between stock prices and intrinsic value. You are "
            "analytical, patient, and willing to wait years for your thesis to play out."
        ),
    },
    "ackman": {
        "name": "Bill Ackman",
        "short": "Ackman",
        "category": "Hedge Fund Managers",
        "style": "Concentrated Value / Activist",
        "quote": "Simple but not easy — buying great businesses at attractive prices and holding them.",
        "system": (
            "You are Bill Ackman, founder of Pershing Square Capital Management. You run a "
            "highly-concentrated portfolio (8-12 stocks) of simple, predictable, and durable "
            "businesses. You often take an activist role, engaging with management to improve "
            "strategy, capital allocation, or governance. You make large, public bets and explain "
            "them in detailed presentations. You are willing to hold through severe drawdowns "
            "when your conviction is high. You are articulate, persistent, and think in decades."
        ),
    },
    "icahn": {
        "name": "Carl Icahn",
        "short": "Icahn",
        "category": "Hedge Fund Managers",
        "style": "Corporate Raider / Activist",
        "quote": "I make money by buying companies that are undervalued and then trying to fix them.",
        "system": (
            "You are Carl Icahn, the original corporate raider turned activist investor. "
            "You target companies with poor management, excess cash, or inefficient structures. "
            "You push for share buybacks, dividend increases, spin-offs, or sales of the company. "
            "You are aggressive, patient, and relentless. You are not afraid of a fight and "
            "have taken on some of the largest companies in America. You focus on asset value "
            "and what a company is worth if properly managed."
        ),
    },
    "tepper": {
        "name": "David Tepper",
        "short": "Tepper",
        "category": "Hedge Fund Managers",
        "style": "Opportunistic / Distressed",
        "quote": "The market is a two-way street. You can make money on the upside and the downside.",
        "system": (
            "You are David Tepper, founder of Appaloosa Management. You specialize in distressed "
            "debt and special situations. You are known for making bold, contrarian macro calls — "
            "buying bank stocks in 2009, for example. You are opportunistic, moving between "
            "asset classes and geographies as opportunities arise. You study central bank policy "
            "closely and believe the Fed is the most important factor in short-term market moves."
        ),
    },
    "cooperman": {
        "name": "Leon Cooperman",
        "short": "Cooperman",
        "category": "Hedge Fund Managers",
        "style": "Value / Catalyst",
        "quote": "I'm a value investor with a catalyst. I want to know what's going to make the stock go up.",
        "system": (
            "You are Leon Cooperman, founder of Omega Advisors and former Goldman Sachs partner. "
            "You are a value investor who requires a catalyst — a specific event or change "
            "that will unlock a stock's value. You favor companies with strong free cash flow, "
            "share buybacks, and insider buying. You are pragmatic, experienced, and focus on "
            "risk-reward ratios. You are skeptical of hype and prefer proven business models "
            "with clear paths to value realization."
        ),
    },
    "yellen": {
        "name": "Janet Yellen",
        "short": "Yellen",
        "category": "Economic",
        "style": "Central Banking / Labor Economics",
        "quote": "I think the best way to promote growth and reduce inequality is through monetary policy.",
        "system": (
            "You are Janet Yellen, former Federal Reserve Chair and Treasury Secretary. "
            "You focus on the dual mandate: maximum employment and price stability. "
            "You analyze labor markets, inflation expectations, wage growth, and financial stability risks. "
            "You believe in evidence-based monetary policy, gradualism, and clear communication. "
            "You are concerned with income inequality and the distributional effects of policy."
        ),
    },
    "bernanke": {
        "name": "Ben Bernanke",
        "short": "Bernanke",
        "category": "Economic",
        "style": "Monetary Policy / Great Depression Scholar",
        "quote": "The Great Depression was caused by the failure of central banks to provide liquidity.",
        "system": (
            "You are Ben Bernanke, former Federal Reserve Chair and scholar of the Great Depression. "
            "You led the Fed through the 2008 financial crisis, pioneering quantitative easing and "
            "forward guidance. You believe central banks must be aggressive in providing liquidity "
            "during financial crises. You study the relationship between financial markets and the "
            "real economy. You emphasize the importance of bank health, credit channels, and "
            "the role of expectations in shaping economic outcomes."
        ),
    },
    "greenspan": {
        "name": "Alan Greenspan",
        "short": "Greenspan",
        "category": "Economic",
        "style": "Free Market / Data-Driven",
        "quote": "If I seem unduly clear to you, you must have misunderstood what I said.",
        "system": (
            "You are Alan Greenspan, former Federal Reserve Chair known for 'Greenspeak' — "
            "deliberately ambiguous communication. You believe in free markets, deregulation, "
            "and the ability of markets to self-correct. You focus on productivity growth, "
            "technological change, and their impact on the economy. You are known for your "
            "data-driven approach, poring over hundreds of data series. You believe the economy "
            "is complex and humility about predictions is essential."
        ),
    },
    "roubini": {
        "name": "Nouriel Roubini",
        "short": "Roubini",
        "category": "Economic",
        "style": "Permabear / Crisis Forecaster",
        "quote": "The economy is facing a perfect storm of risks.",
        "system": (
            "You are Nouriel Roubini, known as 'Dr. Doom' for predicting the 2008 financial crisis. "
            "You focus on systemic risks, debt levels, and vulnerabilities in the global financial "
            "system. You are bearish by nature — you see bubbles, imbalances, and risks that "
            "others miss. You analyze global imbalances, currency wars, and the build-up of "
            "unsustainable debt. You believe in stress-testing economic scenarios and "
            "preparing for worst-case outcomes."
        ),
    },
    "krugman": {
        "name": "Paul Krugman",
        "short": "Krugman",
        "category": "Economic",
        "style": "New Keynesian / Trade Theory",
        "quote": "Productivity isn't everything, but in the long run it is almost everything.",
        "system": (
            "You are Paul Krugman, Nobel Prize-winning economist and New York Times columnist. "
            "You are a New Keynesian economist who believes in fiscal stimulus during recessions "
            "and monetary policy easing when the economy is weak. You work on international trade, "
            "economic geography, and currency crises. You are concerned with inequality, inadequate "
            "demand, and the limits of austerity. You believe government has a critical role in "
            "stabilizing the economy."
        ),
    },
    "musk": {
        "name": "Elon Musk",
        "short": "Musk",
        "category": "Tech / Innovation",
        "style": "First Principles / High Risk Innovation",
        "quote": "If something is important enough, you should try even if the probable outcome is failure.",
        "system": (
            "You are Elon Musk, CEO of Tesla, SpaceX, and xAI. You think from first principles — "
            "boil things down to the fundamental truths and reason up from there. You invest in "
            "companies solving massive problems (sustainable energy, space exploration, AI). "
            "You are aggressive, ambitious, and willing to risk everything on revolutionary ideas. "
            "You focus on technology inflection points, manufacturing scale, and long-term "
            "vision over short-term profits. You are optimistic about technology solving humanity's challenges."
        ),
    },
    "andreessen": {
        "name": "Marc Andreessen",
        "short": "Andreessen",
        "category": "Tech / Innovation",
        "style": "Venture / Software Eating the World",
        "quote": "Software is eating the world.",
        "system": (
            "You are Marc Andreessen, co-founder of Netscape and Andreessen Horowitz. "
            "You believe software companies will transform every industry. You look for "
            "technology businesses with network effects, high gross margins, and large "
            "addressable markets. You are a long-term bull on AI, crypto, and biotech. "
            "You believe the best companies are those that create new markets rather than "
            "compete in existing ones. You are optimistic, contrarian, and think in decades."
        ),
    },
}

PERSONAS = PERSONA_DEFS


def get_persona(key: str) -> dict | None:
    return PERSONAS.get(key.lower().replace(" ", "_").replace("-", "_"))


def list_personas_by_category() -> dict[str, list[dict]]:
    cats: dict[str, list[dict]] = {}
    for key, p in PERSONAS.items():
        cat = p.get("category", "Other")
        if cat not in cats:
            cats[cat] = []
        cats[cat].append({"key": key, **p})
    return cats


def ask_persona(
    persona_key: str,
    question: str,
    llm,
    task_type: str = "action",
    research_session=None,
    *,
    live_data_block: str | None = None,
    agent=None,
    explicit_tickers: list[str] | None = None,
) -> str:
    persona = get_persona(persona_key)
    if not persona:
        return f"[red]Unknown persona: {persona_key}. Use /personas to list available.[/red]"

    system_content = persona["system"]
    if research_session is not None:
        from ..research.tool_registry import build_compact_tool_descriptions

        rules = research_session.rules_prefix()
        tools_hint = build_compact_tool_descriptions()
        system_content = (
            f"{rules}"
            f"{persona['system']}\n\n"
            "## Rallies data tools (for context)\n\n"
            f"{tools_hint}\n"
        ).strip()

    if live_data_block is None:
        from .persona_market import build_persona_live_data_block

        registry = getattr(agent, "data_registry", None) if agent else None
        live_data_block = build_persona_live_data_block(
            explicit_tickers,
            question=question,
            data_registry=registry,
            agent=agent,
            research_session=research_session,
        )

    user_body = (
        f"Analyze from your perspective: {question}\n\n"
        f"Be true to your investment philosophy. Give your analysis, verdict, "
        f"and reasoning. Be specific and include numbers where relevant. "
        f"Keep your answer concise but thorough."
    )
    if live_data_block:
        user_body = f"{live_data_block}{user_body}"

    messages: list[dict] = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_body},
    ]

    from ..llm import LLMError
    try:
        if research_session is not None:
            tickers_note = ""
            if explicit_tickers:
                if len(explicit_tickers) <= 12:
                    tickers_note = f" tickers={','.join(explicit_tickers)}"
                else:
                    head = ",".join(explicit_tickers[:12])
                    tickers_note = (
                        f" tickers={head}+{len(explicit_tickers) - 12}more"
                    )
            research_session.scratchpad.add_thinking(
                f"Persona /ask: {persona_key}{tickers_note}"
            )
        result = llm.prompt(messages, task_type=task_type)
        text = str(result) if not isinstance(result, str) else result
        if research_session is not None:
            research_session.record_llm_tool(
                "persona_llm",
                {"persona": persona_key, "question": question[:500]},
                text,
            )
        return text
    except LLMError as e:
        from ..llm_user_message import format_llm_error_rich

        model = getattr(llm, "last_model", None)
        return format_llm_error_rich(e, model=model)


def debate_personas(
    persona_a: str,
    persona_b: str,
    question: str,
    llm,
    *,
    live_data_block: str | None = None,
    agent=None,
    research_session=None,
) -> tuple[str, str, str, str]:
    if live_data_block is None:
        from .persona_market import build_persona_live_data_block

        registry = getattr(agent, "data_registry", None) if agent else None
        live_data_block = build_persona_live_data_block(
            None,
            question=question,
            data_registry=registry,
            agent=agent,
            research_session=research_session,
        )

    response_a = ask_persona(
        persona_a,
        question,
        llm,
        live_data_block=live_data_block,
        agent=agent,
        research_session=research_session,
    )
    a_persona = get_persona(persona_a) or {}
    b_persona = get_persona(persona_b) or {}
    a_name = a_persona.get("name", persona_a)
    b_name = b_persona.get("name", persona_b)

    b_system = b_persona["system"] if b_persona else ""
    if research_session is not None:
        b_system = f"{research_session.rules_prefix()}{b_system}".strip()

    rebuttal_user = (
        f"Your colleague {a_name} was asked: {question}\n\n"
        f"They responded:\n{response_a}\n\n"
        f"Now it's your turn. Do you agree or disagree with {a_name}? "
        f"Provide your own analysis from your perspective. Be specific about "
        f"where you differ and why. Use the live market data below for current "
        f"figures — do not rely on stale training prices."
    )
    if live_data_block:
        rebuttal_user = f"{live_data_block}{rebuttal_user}"

    rebuttal_messages: list[dict] = [
        {"role": "system", "content": b_system},
        {"role": "user", "content": rebuttal_user},
    ]

    from ..llm import LLMError
    try:
        result = llm.prompt(rebuttal_messages, task_type="action")
        response_b = str(result) if not isinstance(result, str) else result
    except LLMError as e:
        from ..llm_user_message import format_llm_error_rich

        model = getattr(llm, "last_model", None)
        response_b = format_llm_error_rich(e, model=model)

    return response_a, response_b, a_name, b_name


def _persona_keys_by_category() -> dict[str, list[str]]:
    """Map investing category → persona keys registered in PERSONAS."""
    by_cat: dict[str, list[str]] = {}
    for key, p in PERSONAS.items():
        cat = p.get("category")
        if cat:
            by_cat.setdefault(cat, []).append(key)
    return by_cat


def get_consensus_panel(*, seed: int | None = None) -> list[dict]:
    """
    Return one persona per investing category for the consensus panel.

    Randomly picks an expert from each category, then shuffles panel order.
    Pass seed for reproducible selection (tests).
    """
    rng = random.Random(seed)
    by_cat = _persona_keys_by_category()
    panel: list[dict] = []

    for category in CONSENSUS_CATEGORIES:
        candidates = list(by_cat.get(category, []))
        if not candidates:
            fallback = _CONSENSUS_DEFAULT_BY_CATEGORY.get(category)
            if fallback:
                candidates = [fallback]
        if not candidates:
            continue
        key = rng.choice(candidates)
        persona = get_persona(key)
        if persona:
            panel.append({"key": key, "category": category, **persona})

    rng.shuffle(panel)
    return panel


def _format_market_context(tickers: list[str], data_registry=None) -> str:
    """Build compact market context for consensus prompts (no LLM)."""
    if not data_registry or not tickers:
        return ""
    lines = ["Market context (use in your analysis):"]
    yfs = data_registry.get_source("yfinance")
    if not yfs:
        return ""
    from ..quotes import format_yfinance_quote_line

    for ticker in tickers:
        data = yfs.get_quote(ticker)
        if not data or data.get("error"):
            continue
        lines.append(format_yfinance_quote_line(data))
    return "\n".join(lines) if len(lines) > 1 else ""


def _consensus_question(
    tickers: list[str],
    market_context: str = "",
    *,
    ranking_instruction: str = "",
) -> str:
    """Same depth as /ask — full analysis, not a short template."""
    ticker_list = ", ".join(tickers)
    if len(tickers) == 1:
        question = (
            f"Should I invest in {ticker_list}? "
            f"Give your complete investment analysis for {ticker_list}."
        )
    else:
        question = (
            f"Analyze each of these stocks as potential investments: {ticker_list}. "
            f"For every ticker, write a full stand-alone analysis with valuation, "
            f"risks, competitive position, and a clear final verdict."
        )
    if ranking_instruction.strip():
        question += (
            f"\n\nUser ranking request: {ranking_instruction.strip()}\n"
            "After analyzing each ticker, order them from most to least recommended "
            "according to this request."
        )
    if market_context:
        question += f"\n\n{market_context}"
    question += (
        "\n\nUse the official company names from the live data block (ticker + name); "
        "do not guess the business from the ticker symbol alone. "
        "Be true to your investment philosophy. Give your analysis, verdict, "
        "and reasoning. Be specific and include numbers where relevant. "
        "Keep your answer thorough (like a detailed research note). "
        "End with an explicit verdict per stock: Strong Buy, Buy, Hold, Sell, or Strong Sell."
    )
    return question


def _extract_verdict_from_text(text: str) -> str:
    """Best-effort verdict from structured or prose responses (/ask style)."""
    if not text:
        return "Unclear"

    head = text[:2000]
    tail = text[-2500:]
    for block in (tail, head, text):
        m = _VERDICT_RE.search(block)
        if m:
            return m.group(1).strip()

        m2 = re.search(
            r"(?:bottom[- ]?line|final|overall|my)\s+verdict\s*:?\s*"
            r"(Strong Buy|Strong Sell|Buy|Hold|Sell|Not a buy|Avoid|Pass)",
            block,
            re.IGNORECASE,
        )
        if m2:
            v = m2.group(1).strip()
            if "not a buy" in v.lower() or v.lower() in ("avoid", "pass"):
                return "Sell"
            return v.title() if v.lower() in ("buy", "hold", "sell") else v

        for pattern, label in (
            (r"\bstrong\s+sell\b", "Strong Sell"),
            (r"\bstrong\s+buy\b", "Strong Buy"),
            (r"\bwould\s+not\s+buy\b", "Sell"),
            (r"\b(?:stay\s+out|would\s+avoid|pass\s+on)\b", "Sell"),
            (r"\bnot\s+a\s+buy\b", "Sell"),
            (r"\bwould\s+buy\b", "Buy"),
            (r"\b(?:recommend\s+)?hold\b", "Hold"),
        ):
            if re.search(pattern, block, re.IGNORECASE):
                return label

    return "Unclear"


def parse_consensus_response(text: str, tickers: list[str]) -> dict[str, dict]:
    """Parse per-ticker verdict blocks from a persona response."""
    results: dict[str, dict] = {}
    if not text:
        return results

    for ticker in tickers:
        pattern = re.compile(
            rf"##\s*{re.escape(ticker)}\s*([\s\S]*?)(?=\n##\s+[A-Z]|\Z)",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        block = match.group(1).strip() if match else (text.strip() if len(tickers) == 1 else "")

        verdict_m = _VERDICT_RE.search(block)
        conf_m = _CONFIDENCE_RE.search(block)
        sum_m = _SUMMARY_RE.search(block)

        verdict = verdict_m.group(1).strip() if verdict_m else _extract_verdict_from_text(block)
        confidence = conf_m.group(1).strip() if conf_m else "Medium"
        summary = sum_m.group(1).strip() if sum_m else block.strip()[:500]

        results[ticker] = {
            "verdict": verdict,
            "confidence": confidence,
            "summary": summary,
        }
    return results


def ask_persona_consensus(
    persona_key: str,
    tickers: list[str],
    llm,
    market_context: str = "",
    *,
    live_data_block: str = "",
    agent=None,
    ranking_instruction: str = "",
) -> dict:
    """Single persona analyzes all tickers; same depth as /ask, isolated from other personas."""
    persona = get_persona(persona_key)
    if not persona:
        return {
            "key": persona_key,
            "error": f"Unknown persona: {persona_key}",
            "tickers": {},
            "raw": "",
        }

    # Rich prefetch replaces the legacy one-line market_context block.
    ctx = market_context if not live_data_block else ""
    question = _consensus_question(
        tickers, ctx, ranking_instruction=ranking_instruction
    )
    raw_text = ask_persona(
        persona_key,
        question,
        llm,
        task_type="consensus",
        live_data_block=live_data_block or None,
        agent=agent,
        explicit_tickers=tickers,
    )
    if raw_text.startswith("[red]"):
        return {
            "key": persona_key,
            "name": persona.get("name", persona_key),
            "category": persona.get("category", ""),
            "error": raw_text,
            "tickers": {},
            "raw": "",
        }

    parsed = parse_consensus_response(raw_text, tickers)
    return {
        "key": persona_key,
        "name": persona["name"],
        "category": persona.get("category", ""),
        "style": persona.get("style", ""),
        "tickers": parsed,
        "raw": raw_text,
        "error": None,
    }


def _build_full_analyses_digest(
    panel_results: list[dict],
    max_chars_per_persona: int = 10000,
) -> str:
    """Full persona analyses for the moderator (each persona run in isolation earlier)."""
    sections = []
    for entry in panel_results:
        if entry.get("error"):
            sections.append(
                f"### {entry.get('name', entry['key'])} ({entry.get('category', '')})\n"
                f"ERROR: {entry['error']}"
            )
            continue
        raw = (entry.get("raw") or "").strip()
        if not raw:
            continue
        if len(raw) > max_chars_per_persona:
            raw = (
                raw[:max_chars_per_persona]
                + "\n\n[... remainder omitted to fit summary context ...]"
            )
        sections.append(
            f"### {entry['name']} ({entry.get('category', '')})\n\n{raw}"
        )
    return "\n\n---\n\n".join(sections)


def format_verdict_matrix_markdown(
    panel_results: list[dict],
    tickers: list[str],
) -> str:
    """Plain markdown verdict matrix for session memory (follow-up context)."""
    if not panel_results or not tickers:
        return ""
    header = "| Expert | Category | " + " | ".join(tickers) + " |"
    sep = "| --- | --- | " + " | ".join(["---"] * len(tickers)) + " |"
    rows: list[str] = []
    for entry in panel_results:
        name = str(entry.get("name") or entry.get("key") or "?")
        cat = str(entry.get("category") or "")
        if entry.get("error"):
            cells = ["ERROR"] * len(tickers)
        else:
            cells = [
                str(entry.get("tickers", {}).get(t, {}).get("verdict", "—"))
                for t in tickers
            ]
        rows.append("| " + " | ".join([name, cat, *cells]) + " |")
    return "\n".join([header, sep, *rows])


def _format_expert_analyses_for_memory(
    panel_results: list[dict],
    *,
    max_chars_per_persona: int = 4000,
) -> str:
    """Per-expert text so follow-ups can reference a named panelist (e.g. Buffett)."""
    sections: list[str] = []
    for entry in panel_results:
        if entry.get("error"):
            sections.append(
                f"### {entry.get('name', entry.get('key', '?'))} "
                f"({entry.get('category', '')}) "
                f"[{entry.get('key', '')}]\n"
                f"ERROR: {entry['error']}"
            )
            continue
        raw = (entry.get("raw") or "").strip()
        if not raw:
            continue
        if len(raw) > max_chars_per_persona:
            raw = (
                raw[:max_chars_per_persona]
                + "\n\n[... analysis truncated for session memory ...]"
            )
        key = entry.get("key", "")
        sections.append(
            f"### {entry.get('name', key)} ({entry.get('category', '')})"
            f"{f' [{key}]' if key else ''}\n\n{raw}"
        )
    return "\n\n---\n\n".join(sections)


def format_consensus_for_session_memory(
    panel_results: list[dict],
    tickers: list[str],
    summary: str,
    *,
    max_chars_per_persona: int = 4000,
) -> str:
    """
    Rich session-memory payload after /consensus.

    Includes verdict matrix, each expert's analysis (by name/key), and the
    moderator summary so free-form follow-ups can reference e.g. Buffett's view.
    """
    ticker_list = ", ".join(tickers)
    parts = [
        f"# Consensus panel — {ticker_list}",
        "",
        "## Verdict matrix",
        format_verdict_matrix_markdown(panel_results, tickers),
        "",
        "## Expert analyses",
        _format_expert_analyses_for_memory(
            panel_results, max_chars_per_persona=max_chars_per_persona
        ),
        "",
        "## Consensus summary",
        str(summary or "").strip(),
    ]
    return "\n".join(p for p in parts if p is not None).strip()


def format_batched_consensus_for_session_memory(
    panel_batches: list[list[dict]],
    batch_tickers: list[list[str]],
    batch_summaries: list[str],
    master: str,
    *,
    max_chars_per_persona: int = 3000,
) -> str:
    """Session memory for multi-batch /consensus runs."""
    all_tickers = [t for batch in batch_tickers for t in batch]
    parts = [f"# Consensus panel (batched) — {', '.join(all_tickers)}", ""]
    for idx, (batch, panel) in enumerate(zip(batch_tickers, panel_batches), start=1):
        parts.append(f"## Batch {idx} — {', '.join(batch)}")
        parts.append(format_verdict_matrix_markdown(panel, batch))
        parts.append(
            _format_expert_analyses_for_memory(
                panel, max_chars_per_persona=max_chars_per_persona
            )
        )
        if idx - 1 < len(batch_summaries):
            parts.append(f"### Batch {idx} summary\n{batch_summaries[idx - 1].strip()}")
        parts.append("")
    parts.append("## Master consensus")
    parts.append(str(master or "").strip())
    return "\n".join(parts).strip()


def summarize_consensus(
    panel_results: list[dict],
    tickers: list[str],
    llm,
    max_chars_per_persona: int = 10000,
) -> str:
    """Final consensus from full panel analyses (one LLM call, answer budget)."""
    digest = _build_full_analyses_digest(panel_results, max_chars_per_persona)
    if not digest.strip():
        return "[yellow]No persona analyses available to summarize.[/yellow]"

    ticker_list = ", ".join(tickers)
    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "You are a neutral investment committee moderator. "
                "You receive complete analyses from seven experts (one per school of thought). "
                "Each expert wrote independently; synthesize their full reports into one consensus. "
                "Note agreement and meaningful disagreements. Do not invent facts not in the panel."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Stocks under review: {ticker_list}\n\n"
                f"Full panel analyses:\n\n{digest}\n\n"
                f"Write a consensus report with:\n"
                f"1. **Overall consensus** per ticker (aggregate verdict + confidence)\n"
                f"2. **Where experts agree** (cite which schools align)\n"
                f"3. **Key disagreements** (which categories diverge and why)\n"
                f"4. **Actionable takeaway** for a retail investor (not financial advice)\n\n"
                f"Use markdown headers. Be specific and reference the experts' reasoning."
            ),
        },
    ]

    from ..llm import LLMError

    try:
        result = llm.prompt(messages, task_type="consensus_summary")
        return str(result) if not isinstance(result, str) else result
    except LLMError as e:
        from ..llm_user_message import format_llm_error_rich

        model = getattr(llm, "last_model", None)
        return format_llm_error_rich(e, model=model)


def run_consensus_analysis(
    tickers: list[str],
    llm,
    data_registry=None,
    agent=None,
    live_data_block: str | None = None,
    status_callback=None,
    on_persona_complete=None,
    *,
    panel: list[dict] | None = None,
    ranking_instruction: str = "",
) -> tuple[list[dict], str]:
    """
    Run sequential multi-persona consensus for one or more tickers.

    Each panel member runs in isolation (no cross-persona context). Returns
    (panel_results, consensus_summary_markdown).
    """
    tickers = [t.upper().strip() for t in tickers if t and t.strip()]
    if not tickers:
        return [], "[yellow]No tickers provided.[/yellow]"

    from .persona_market import build_persona_live_data_block

    if live_data_block is None:
        live_data_block = build_persona_live_data_block(
            tickers,
            max_tickers=None,
            data_registry=data_registry,
            agent=agent,
        )
    market_context = ""
    if not live_data_block:
        market_context = _format_market_context(tickers, data_registry)
        if market_context and callable(status_callback):
            status_callback(
                "[dim]Using limited quote snapshot (full prefetch unavailable).[/dim]"
            )
    elif callable(status_callback):
        status_callback(
            f"[dim]Loaded live quotes, financials"
            f"{', and SEC filings' if len(tickers) == 1 else ''} "
            f"for {', '.join(tickers)}.[/dim]"
        )

    if panel is None:
        panel = get_consensus_panel()
    panel_size = len(panel)
    panel_results: list[dict] = []

    for idx, entry in enumerate(panel, start=1):
        persona_key = entry["key"]
        category = entry.get("category", "")
        name = entry.get("name") or persona_key
        if callable(status_callback):
            status_callback(
                f"[{idx}/{panel_size}] {name} ({category}) analyzing {', '.join(tickers)}..."
            )

        result = ask_persona_consensus(
            persona_key,
            tickers,
            llm,
            market_context=market_context if not live_data_block else "",
            live_data_block=live_data_block,
            agent=agent,
            ranking_instruction=ranking_instruction,
        )
        panel_results.append(result)

        if callable(on_persona_complete):
            on_persona_complete(result, idx, panel_size)

    if callable(status_callback):
        status_callback(
            f"Building consensus summary from full panel analyses ({panel_size} reports)..."
        )

    summary = summarize_consensus(panel_results, tickers, llm)
    return panel_results, summary
