"""Curated thematic-investing catalog: what each theme is, how its value chain is layered, and which companies sit where.

This is editorial content, written once and reviewed by hand, not data: the numbers on the pages (returns, analyst
targets, growth, valuation) are fetched live; this file supplies the framing. It deliberately contains no price
targets, market-size forecasts or growth numbers, which would go stale or be unsourced.

Roles:
  core      pure plays and the clear leaders: the theme is the main reason to own the stock
  enabler   "picks and shovels": suppliers whose products the theme cannot grow without
  adjacent  large companies that benefit but are not driven by the theme alone
  emerging  small, early or unproven companies; high potential and high risk of permanent loss

`exposure` (1-3) is how much of the business depends on the theme: 3 = most of it, 1 = a minor part.
Companies get acquired, rename and delist: the pages show a name as unavailable if Yahoo has no data for it.
"""

ROLES = {
    "core": {"name": "Core leaders", "blurb": "Pure plays and the clear leaders of the theme"},
    "enabler": {"name": "Picks & shovels", "blurb": "Suppliers the theme cannot grow without"},
    "adjacent": {"name": "Other beneficiaries", "blurb": "Large companies that benefit without depending on the theme"},
    "emerging": {"name": "Emerging & speculative", "blurb": "Small, early or unproven: high potential, high risk of permanent loss"},
}
EDITORIAL_DATE = "October 2026"


def S(symbol, name, layer, role, exposure, why):
    return {"symbol": symbol, "name": name, "layer": layer, "role": role, "exposure": exposure, "why": why}


THEMES = [
    {
        "id": "ai", "name": "Artificial Intelligence", "short": "AI", "color": "#a78bfa", "navId": "themeai",
        "tagline": "Models that write, see, reason and act, and the chips, data centers and power they run on.",
        "thesis": "AI turns computing from something people operate into something that does work for them. Training and running large models needs enormous amounts of specialised chips, memory, networking, data-center space and electricity, so spending flows first to infrastructure, then to the software and services built on it.",
        "whyNow": "Hyperscalers and enterprises are committing multi-year capital budgets to AI capacity, and adoption is moving from experiments to products people pay for.",
        "layers": [
            {"id": "silicon", "name": "Chips & design", "blurb": "GPUs, accelerators and the processors and memory around them"},
            {"id": "foundry", "name": "Manufacturing & equipment", "blurb": "The fabs and machines that make advanced chips"},
            {"id": "infra", "name": "Data-center infrastructure", "blurb": "Servers, networking, cooling and cloud capacity"},
            {"id": "power", "name": "Power", "blurb": "Electricity generation the data centers consume"},
            {"id": "platform", "name": "Models & platforms", "blurb": "The clouds and labs that train and serve models"},
            {"id": "apps", "name": "Software & applications", "blurb": "Products that put AI in front of customers"},
        ],
        "stocks": [
            S("NVDA", "NVIDIA", "silicon", "core", 3, "Dominant maker of the GPUs and software stack used to train and run most AI models."),
            S("MSFT", "Microsoft", "platform", "core", 2, "Azure cloud plus a deep partnership with OpenAI and Copilot products across its software."),
            S("GOOGL", "Alphabet", "platform", "core", 2, "Gemini models, custom TPU chips and Google Cloud, with AI built into Search."),
            S("AMZN", "Amazon", "platform", "core", 2, "AWS is the largest cloud; builds its own AI chips and backs Anthropic."),
            S("META", "Meta Platforms", "platform", "core", 2, "Spends heavily on AI for its ad engine and open-weight Llama models."),
            S("PLTR", "Palantir", "apps", "core", 3, "Sells AI platforms that put models to work inside government and enterprise operations."),
            S("AVGO", "Broadcom", "silicon", "enabler", 2, "Designs custom AI accelerators for hyperscalers and the networking chips that link them."),
            S("AMD", "Advanced Micro Devices", "silicon", "enabler", 2, "Main GPU alternative to NVIDIA, plus server CPUs used throughout AI data centers."),
            S("TSM", "Taiwan Semiconductor", "foundry", "enabler", 2, "Manufactures nearly all leading AI chips, including NVIDIA's."),
            S("ASML", "ASML", "foundry", "enabler", 2, "Sole supplier of the EUV lithography machines advanced chips cannot be made without."),
            S("MU", "Micron Technology", "silicon", "enabler", 2, "High-bandwidth memory is a bottleneck in AI accelerators."),
            S("ARM", "Arm Holdings", "silicon", "enabler", 2, "Licenses the processor designs inside many AI-capable chips and devices."),
            S("MRVL", "Marvell Technology", "silicon", "enabler", 2, "Custom AI silicon and high-speed connectivity for data centers."),
            S("ANET", "Arista Networks", "infra", "enabler", 2, "High-speed network switches linking AI clusters."),
            S("VRT", "Vertiv", "infra", "enabler", 2, "Power and liquid-cooling systems AI racks need."),
            S("DELL", "Dell Technologies", "infra", "enabler", 1, "Builds and ships AI servers to enterprises and cloud providers."),
            S("SMCI", "Super Micro Computer", "infra", "enabler", 2, "Fast-to-market AI server and rack systems."),
            S("ORCL", "Oracle", "platform", "adjacent", 1, "Large AI cloud contracts and database software."),
            S("CEG", "Constellation Energy", "power", "adjacent", 1, "Largest US nuclear fleet; data centers want carbon-free power around the clock."),
            S("VST", "Vistra", "power", "adjacent", 1, "Power generator selling to data-center growth in key US regions."),
            S("NOW", "ServiceNow", "apps", "adjacent", 1, "Enterprise workflow software adding AI agents."),
            S("CRWD", "CrowdStrike", "apps", "adjacent", 1, "Cybersecurity increasingly built on AI; AI also expands what must be defended."),
            S("SNOW", "Snowflake", "apps", "adjacent", 1, "Data platform where companies prepare data for AI."),
            S("CRWV", "CoreWeave", "infra", "emerging", 3, "Specialised AI cloud renting GPUs; heavily indebted and dependent on a few customers."),
            S("NBIS", "Nebius Group", "infra", "emerging", 3, "AI-focused cloud and infrastructure provider."),
            S("APLD", "Applied Digital", "infra", "emerging", 3, "Builds data centers for AI and high-performance computing."),
            S("SOUN", "SoundHound AI", "apps", "emerging", 3, "Voice AI for cars, restaurants and devices; small and loss-making."),
            S("BBAI", "BigBear.ai", "apps", "emerging", 3, "AI analytics for defense and government; small and volatile."),
            S("AI", "C3.ai", "apps", "emerging", 3, "Enterprise AI applications; has struggled to grow profitably."),
            S("TEM", "Tempus AI", "apps", "emerging", 3, "AI-driven precision medicine and clinical data."),
        ],
        "etfs": [("SMH", "VanEck Semiconductor ETF"), ("AIQ", "Global X Artificial Intelligence & Technology ETF"), ("BOTZ", "Global X Robotics & AI ETF")],
        "shortTerm": {
            "catalysts": ["Quarterly capital-spending updates from the largest cloud companies, the best real-time read on demand",
                          "New chip generations ramping and any easing of the memory and packaging bottlenecks",
                          "Evidence that AI products are earning revenue, not just costing money"],
            "risks": ["Spending guided down, or a digestion period after a large build-out",
                      "Export controls and geopolitics around Taiwan and China",
                      "Valuations that already assume years of strong growth, so even good news can disappoint"],
        },
        "longTerm": {
            "drivers": ["AI becoming a normal feature of software, search, coding, customer service and science",
                        "Falling cost per unit of AI compute widening what is worth automating",
                        "Electricity and chips as long-lived constraints that reward whoever can supply them"],
            "risks": ["Returns on the infrastructure built may fall short, leaving overcapacity and write-downs",
                      "Efficiency breakthroughs that reduce hardware demand",
                      "Regulation, copyright and trust problems; profits captured by a few platforms rather than spread"],
        },
        "watch": "Most of the theme's value so far has accrued to infrastructure suppliers. If AI applications start earning real revenue, software companies could become the next leg; if not, expect the infrastructure boom to fade.",
    },
    {
        "id": "robotics", "name": "Robotics & Automation", "short": "Robotics", "color": "#34d399", "navId": "themerobotics",
        "tagline": "Machines that move, lift, weld, operate and increasingly think: from factory arms to surgical systems and humanoids.",
        "thesis": "Aging workforces, labor shortages, reshoring of manufacturing and better AI vision and control are making robots practical in more jobs. Industrial robots are a mature business; the new growth is in warehouses, surgery, inspection, delivery and general-purpose humanoids.",
        "whyNow": "AI has made robots far better at perceiving and adapting to messy real-world settings, and labor costs and supply-chain security are pushing companies to automate.",
        "layers": [
            {"id": "industrial", "name": "Industrial automation", "blurb": "Factory robots, controls and motion systems"},
            {"id": "logistics", "name": "Warehouse & logistics", "blurb": "Automated storage, picking and delivery"},
            {"id": "medical", "name": "Medical robotics", "blurb": "Surgical and assistive systems"},
            {"id": "vision", "name": "Sensors & vision", "blurb": "Cameras, lidar and machine-vision software"},
            {"id": "brains", "name": "Compute & AI", "blurb": "Chips and models that let robots perceive and decide"},
            {"id": "humanoid", "name": "General-purpose & humanoid", "blurb": "Early-stage robots meant for many tasks"},
        ],
        "stocks": [
            S("ISRG", "Intuitive Surgical", "medical", "core", 3, "Maker of the da Vinci surgical system with a large installed base and recurring instrument sales."),
            S("TER", "Teradyne", "industrial", "core", 2, "Owns Universal Robots (collaborative robots) alongside its chip-testing business."),
            S("ROK", "Rockwell Automation", "industrial", "core", 3, "Factory automation hardware and software."),
            S("ABBNY", "ABB", "industrial", "core", 2, "Industrial robots and electrification; one of the largest robot makers."),
            S("FANUY", "Fanuc", "industrial", "core", 3, "World's largest industrial-robot and CNC maker."),
            S("SYM", "Symbotic", "logistics", "core", 3, "Automated warehouse systems, largely for one very large retailer."),
            S("TSLA", "Tesla", "humanoid", "core", 1, "Developing the Optimus humanoid; the stock is driven mostly by cars and energy."),
            S("NVDA", "NVIDIA", "brains", "enabler", 1, "Chips and simulation tools used to train and run robot AI."),
            S("CGNX", "Cognex", "vision", "enabler", 3, "Machine-vision systems that let factory robots see and inspect."),
            S("ZBRA", "Zebra Technologies", "logistics", "enabler", 2, "Scanners, mobile computers and warehouse automation."),
            S("EMR", "Emerson Electric", "industrial", "enabler", 2, "Control systems and software for automated plants."),
            S("ON", "ON Semiconductor", "vision", "enabler", 1, "Image sensors and power chips for robots and vehicles."),
            S("AMBA", "Ambarella", "vision", "enabler", 2, "Vision-processing chips for cameras and autonomous machines."),
            S("PRCT", "PROCEPT BioRobotics", "medical", "core", 3, "Robotic water-jet surgery for enlarged prostate."),
            S("PATH", "UiPath", "industrial", "adjacent", 1, "Software robots that automate office tasks."),
            S("HSAI", "Hesai Group", "vision", "emerging", 3, "Lidar sensors for vehicles and robots; China-based."),
            S("OUST", "Ouster", "vision", "emerging", 3, "Lidar for robots and industrial use; small and loss-making."),
            S("SERV", "Serve Robotics", "logistics", "emerging", 3, "Sidewalk delivery robots; very early revenue."),
            S("RR", "Richtech Robotics", "humanoid", "emerging", 3, "Service robots for restaurants and hotels; micro-cap."),
            S("IRBT", "iRobot", "industrial", "emerging", 3, "Robot vacuum pioneer in financial difficulty: a cautionary example."),
        ],
        "etfs": [("BOTZ", "Global X Robotics & AI ETF"), ("ROBO", "ROBO Global Robotics & Automation ETF"), ("ARKQ", "ARK Autonomous Technology & Robotics ETF")],
        "shortTerm": {
            "catalysts": ["Manufacturing orders and capital spending recovering after a soft stretch in industrial demand",
                          "Humanoid and warehouse-robot pilots turning into paid deployments",
                          "Surgical-robot procedure growth and new system launches"],
            "risks": ["Weak factory investment, especially in autos and electronics",
                      "Tariffs and trade tension disrupting supply chains and demand",
                      "Hype around humanoids running ahead of real revenue"],
        },
        "longTerm": {
            "drivers": ["Shrinking working-age populations making automation a necessity",
                        "Robots getting cheaper and easier to program, opening small and mid-sized customers",
                        "AI giving robots the flexibility to handle varied tasks, not just repeat one"],
            "risks": ["Humanoids and general-purpose robots may take far longer to be useful and affordable than expected",
                      "Chinese manufacturers competing hard on price",
                      "Cyclical demand: automation spending falls sharply in recessions"],
        },
        "watch": "The mature industrial-robot makers are cyclical and fairly valued; the big upside, and the big risk, is in whether general-purpose robots become genuinely useful. Be wary of micro-caps priced as if that is already solved.",
    },
    {
        "id": "quantum", "name": "Quantum Computing", "short": "Quantum", "color": "#38bdf8", "navId": "themequantum",
        "tagline": "Computers that use quantum physics to attack problems classical machines cannot, still early and pre-profit.",
        "thesis": "If error-corrected quantum computers are built, they could transform chemistry, materials, optimisation and cryptography. Today's machines are small and error-prone, and the commercial revenue is tiny, so the sector trades on progress milestones and sentiment rather than earnings.",
        "whyNow": "Recent advances in error correction and rising government and corporate funding have brought the first credible roadmaps to useful, fault-tolerant machines.",
        "layers": [
            {"id": "hardware", "name": "Quantum hardware", "blurb": "Trapped-ion, superconducting, annealing and photonic machines"},
            {"id": "cloud", "name": "Cloud access & software", "blurb": "Platforms to program and rent quantum machines"},
            {"id": "components", "name": "Components & test", "blurb": "Lasers, cryogenics, photonics and measurement equipment"},
            {"id": "classical", "name": "Classical computing", "blurb": "Chips and tools that work alongside quantum machines"},
            {"id": "security", "name": "Post-quantum security", "blurb": "Defences against future quantum codebreaking"},
        ],
        "stocks": [
            S("IONQ", "IonQ", "hardware", "core", 3, "Trapped-ion quantum computers sold through major clouds; has been acquiring other quantum companies."),
            S("RGTI", "Rigetti Computing", "hardware", "core", 3, "Superconducting quantum chips; small revenue, heavy losses."),
            S("QBTS", "D-Wave Quantum", "hardware", "core", 3, "Quantum annealing systems for optimisation problems; early commercial customers."),
            S("QUBT", "Quantum Computing Inc.", "hardware", "emerging", 3, "Photonic quantum devices; tiny revenue and a volatile stock."),
            S("IBM", "IBM", "hardware", "core", 1, "Long-running superconducting quantum program and cloud access; the stock is about much more."),
            S("GOOGL", "Alphabet", "hardware", "adjacent", 1, "Google Quantum AI has led several error-correction milestones."),
            S("MSFT", "Microsoft", "cloud", "adjacent", 1, "Azure Quantum platform and its own topological-qubit research."),
            S("AMZN", "Amazon", "cloud", "adjacent", 1, "Braket service gives cloud access to several quantum machines."),
            S("HON", "Honeywell", "hardware", "adjacent", 1, "Owns a large stake in Quantinuum, a leading trapped-ion company."),
            S("NVDA", "NVIDIA", "classical", "enabler", 1, "GPUs and software used to simulate quantum systems and control hardware."),
            S("KEYS", "Keysight Technologies", "components", "enabler", 1, "Test and measurement gear used to build and verify quantum systems."),
            S("FORM", "FormFactor", "components", "enabler", 1, "Probe cards and cryogenic test systems relevant to quantum chips."),
            S("COHR", "Coherent", "components", "enabler", 1, "Lasers and photonics used in several quantum approaches."),
            S("ARQQ", "Arqit Quantum", "security", "emerging", 3, "Quantum-safe encryption software; micro-cap."),
            S("LAES", "SEALSQ", "security", "emerging", 3, "Post-quantum secure chips; small and speculative."),
        ],
        "etfs": [("QTUM", "Defiance Quantum ETF")],
        "shortTerm": {
            "catalysts": ["Hardware milestones: more qubits, lower error rates, demonstrated error correction",
                          "Government contracts and funding programs",
                          "Acquisitions and partnerships among the small pure plays"],
            "risks": ["Share sales and convertible debt: pre-profit companies raise money when their stocks are high",
                      "Sentiment swings of 50% or more in weeks",
                      "Announcements that overstate how close useful machines are"],
        },
        "longTerm": {
            "drivers": ["Fault-tolerant machines enabling drug and materials discovery, logistics and finance applications",
                        "Government demand tied to security and national competitiveness",
                        "A few architectures winning, concentrating value in the survivors"],
            "risks": ["Useful machines may take a decade or more; most current companies may not survive that long",
                      "Large, rich competitors (Google, IBM, Microsoft) can outspend the small pure plays",
                      "The winning technology may not be the one a given company has bet on"],
        },
        "watch": "This is the most speculative of the four themes. Revenue is minimal, and many of these stocks have risen several-fold on sentiment. Size positions as option-like bets you can afford to lose, and favour firms with years of cash.",
    },
    {
        "id": "space", "name": "Space Exploration", "short": "Space", "color": "#fb923c", "navId": "themespace",
        "tagline": "Launch, satellites, lunar missions and the defense and communications business around them.",
        "thesis": "Reusable rockets have cut the cost of reaching orbit, which makes satellite constellations, direct-to-phone connectivity, Earth observation and lunar missions commercially plausible. Government defense and space budgets provide a steady base underneath the speculative growth.",
        "whyNow": "Launch rates are at record highs, governments are buying more space-based defense and communications, and a new wave of space companies has gone public.",
        "layers": [
            {"id": "launch", "name": "Launch", "blurb": "Rockets and the ranges that fly them"},
            {"id": "satellites", "name": "Satellite manufacturing & components", "blurb": "Spacecraft, sensors and subsystems"},
            {"id": "comms", "name": "Satellite communications", "blurb": "Broadband, phone and data links from orbit"},
            {"id": "earthobs", "name": "Earth observation & data", "blurb": "Imagery and analytics from space"},
            {"id": "defense", "name": "Defense & government", "blurb": "Prime contractors for military and civil space"},
            {"id": "lunar", "name": "Lunar & in-space services", "blurb": "Landers, stations and in-orbit services"},
        ],
        "stocks": [
            S("RKLB", "Rocket Lab", "launch", "core", 3, "Small-launch leader building a larger reusable rocket and a spacecraft manufacturing business."),
            S("ASTS", "AST SpaceMobile", "comms", "core", 3, "Building a satellite network to give ordinary phones broadband; pre-scale and capital-hungry."),
            S("PL", "Planet Labs", "earthobs", "core", 3, "Daily satellite imagery sold by subscription."),
            S("LUNR", "Intuitive Machines", "lunar", "core", 3, "Commercial lunar landers and NASA contracts."),
            S("RDW", "Redwire", "satellites", "core", 3, "Space infrastructure and components for civil and defense customers."),
            S("FLY", "Firefly Aerospace", "launch", "core", 3, "Launch vehicles and lunar landers; recently public."),
            S("VOYG", "Voyager Technologies", "defense", "core", 3, "Defense and commercial space technology; recently public."),
            S("KRMN", "Karman Holdings", "satellites", "enabler", 3, "Subsystems for missiles, defense and space; recently public."),
            S("LMT", "Lockheed Martin", "defense", "adjacent", 1, "Satellites, missile defense and Orion; very large defense contractor."),
            S("NOC", "Northrop Grumman", "defense", "adjacent", 1, "Space systems, solid rocket motors and satellites."),
            S("BA", "Boeing", "defense", "adjacent", 1, "Starliner, SLS and satellites inside a troubled larger business."),
            S("LHX", "L3Harris Technologies", "defense", "adjacent", 1, "Space sensors and communications for defense customers."),
            S("TDY", "Teledyne Technologies", "satellites", "enabler", 1, "Imaging sensors and instruments for space and defense."),
            S("IRDM", "Iridium Communications", "comms", "adjacent", 2, "Global satellite voice and data network with steady subscriptions."),
            S("GSAT", "Globalstar", "comms", "adjacent", 2, "Satellite network supporting phone emergency features."),
            S("VSAT", "Viasat", "comms", "adjacent", 2, "Satellite broadband and government communications; leveraged."),
            S("SATL", "Satellogic", "earthobs", "emerging", 3, "Earth-observation satellites; small and loss-making."),
            S("BKSY", "BlackSky Technologies", "earthobs", "emerging", 3, "Rapid-revisit imagery for defense and intelligence customers."),
            S("SPCE", "Virgin Galactic", "launch", "emerging", 3, "Space tourism that has yet to prove a viable business."),
        ],
        "etfs": [("UFO", "Procure Space ETF"), ("ARKX", "ARK Space Exploration & Innovation ETF"), ("ROKT", "SPDR S&P Kensho Final Frontiers ETF")],
        "shortTerm": {
            "catalysts": ["Launch cadence and first flights of new reusable rockets",
                          "Government budgets and contract awards for defense space, lunar missions and satellite networks",
                          "Satellite network milestones: constellations launched, commercial service started"],
            "risks": ["Launch failures and delays, which hurt small companies out of proportion",
                      "Equity raises: capital-hungry companies sell shares into rallies",
                      "A large private competitor (SpaceX is not listed) setting prices and pace"],
        },
        "longTerm": {
            "drivers": ["Cheap, frequent launch making space-based infrastructure economic",
                        "Satellite connectivity and Earth observation becoming standard services",
                        "Lunar and in-orbit industry, if government anchor customers keep funding it"],
            "risks": ["The largest, most profitable part of space is private, so listed companies may capture less of the value",
                      "Government budgets are political and can change quickly",
                      "Long timelines to profit for companies that need repeated financing"],
        },
        "watch": "Defense primes anchor the theme with steady cash flows; the pure plays offer the growth, and the risk. Check who the customers are: dependence on one government contract or one large customer is the common weak point.",
    },
]

BY_ID = {t["id"]: t for t in THEMES}


def all_symbols() -> list[str]:
    """Every stock and ETF across all themes, plus the SPY benchmark, de-duplicated."""
    seen, out = set(), []
    for t in THEMES:
        for s in [x["symbol"] for x in t["stocks"]] + [e[0] for e in t["etfs"]]:
            if s not in seen:
                seen.add(s)
                out.append(s)
    return out + ([] if "SPY" in seen else ["SPY"])


def stock_symbols() -> list[str]:
    """Companies only (ETFs have no fundamentals to fetch)."""
    seen, out = set(), []
    for t in THEMES:
        for x in t["stocks"]:
            if x["symbol"] not in seen:
                seen.add(x["symbol"])
                out.append(x["symbol"])
    return out
