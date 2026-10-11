"""Curated thematic-investing catalog: what each theme is, how its value chain is layered, and which companies sit where.

This is editorial content, written once and reviewed by hand, not data: the numbers on the pages (returns, analyst
targets, growth, valuation) are fetched live; this file supplies the framing. It deliberately contains no price
targets, market-size forecasts or growth numbers, which would go stale or be unsourced.

Roles:
  core      pure plays and the clear leaders: the theme is the main reason to own the stock
  enabler   "picks and shovels": suppliers whose products the theme cannot grow without
  adjacent  large companies that benefit but are not driven by the theme alone
  emerging  small, early or unproven companies; high potential and high risk of permanent loss
  atrisk    companies the theme could undercut (only on themes where disruption is the point); displayed, but excluded
            from the basket, the analyst outlook and the candidate ranking so they never read as recommendations

`exposure` (1-3) is how much of the business depends on the theme: 3 = most of it, 1 = a minor part.
Companies get acquired, rename and delist: the pages show a name as unavailable if Yahoo has no data for it.
"""

ROLES = {
    "core": {"name": "Core leaders", "blurb": "Pure plays and the clear leaders of the theme"},
    "enabler": {"name": "Picks & shovels", "blurb": "Suppliers the theme cannot grow without"},
    "adjacent": {"name": "Other beneficiaries", "blurb": "Large companies that benefit without depending on the theme"},
    "emerging": {"name": "Emerging & speculative", "blurb": "Small, early or unproven: high potential, high risk of permanent loss"},
    "atrisk": {"name": "At risk of disruption", "blurb": "Businesses the theme could undercut; shown for contrast and left out of the basket, outlook and candidate rankings"},
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
    {
        "id": "abundance", "name": "AI Abundance", "short": "Abundance", "color": "#f472b6", "navId": "themeabundance",
        "tagline": "If intelligence, labor and energy become cheap and plentiful: what changes for jobs, for markets, and who is best placed.",
        "thesis": "The abundance argument is that AI and robots could make cognitive work, physical labor, scientific discovery and eventually energy dramatically cheaper, so that goods and services once limited by human time become plentiful. If it happens, the gains go first to whoever owns the scarce inputs (compute, power, data, distribution and trust), while businesses that sell human hours at a markup are squeezed. It is a scenario, not a forecast: the pace, and who captures the gains, are both uncertain.",
        "whyNow": "The cost of AI capability per dollar has been falling fast, capital is flowing into power and compute, and companies are starting to replace routine knowledge work with software.",
        "layers": [
            {"id": "intelligence", "name": "Cheap intelligence", "blurb": "The chips, clouds and models that make thinking inexpensive"},
            {"id": "labor", "name": "Automated labor", "blurb": "Robots and machines doing physical and medical work"},
            {"id": "energy", "name": "Abundant energy", "blurb": "Power generation that data centers and automation consume"},
            {"id": "science", "name": "Science & health", "blurb": "Faster drug discovery, diagnostics and surgery"},
            {"id": "scarce", "name": "Scarce inputs & assets", "blurb": "Materials and physical infrastructure that stay limited"},
            {"id": "distribution", "name": "Distribution & trust", "blurb": "Networks, payments and brands that keep their pricing power"},
            {"id": "disrupted", "name": "At risk of disruption", "blurb": "Businesses that sell routine human hours"},
        ],
        "stocks": [
            S("NVDA", "NVIDIA", "intelligence", "core", 3, "Sells the compute that makes machine intelligence possible; the clearest owner of a scarce input."),
            S("GOOGL", "Alphabet", "intelligence", "core", 2, "Models, custom chips, a cloud, and distribution to billions of users."),
            S("MSFT", "Microsoft", "intelligence", "core", 2, "Cloud, models and the software workers already use every day."),
            S("TSLA", "Tesla", "labor", "core", 1, "Autonomy and a humanoid robot program; the stock is driven mostly by cars and energy."),
            S("ISRG", "Intuitive Surgical", "labor", "core", 2, "Robotic surgery, an early example of machines extending skilled labor."),
            S("GEV", "GE Vernova", "energy", "enabler", 2, "Gas turbines, grid equipment and wind: the hardware of added power capacity."),
            S("CEG", "Constellation Energy", "energy", "enabler", 2, "Nuclear fleet supplying around-the-clock carbon-free power."),
            S("NEE", "NextEra Energy", "energy", "enabler", 2, "Largest renewable developer with a regulated utility base."),
            S("CCJ", "Cameco", "energy", "enabler", 3, "Uranium miner: fuel for a nuclear build-out if one materialises."),
            S("FCX", "Freeport-McMoRan", "scarce", "enabler", 2, "Copper, which electrification, grids and data centers all need and cannot easily replace."),
            S("EQIX", "Equinix", "scarce", "enabler", 2, "Data-center real estate and interconnection."),
            S("VRT", "Vertiv", "scarce", "enabler", 2, "Power and cooling gear that every dense compute site needs."),
            S("LLY", "Eli Lilly", "science", "adjacent", 1, "Scaling obesity and diabetes drugs and using AI in discovery."),
            S("AMZN", "Amazon", "distribution", "adjacent", 1, "Cloud, logistics and robots at scale; a distributor that can pass on cheaper costs."),
            S("V", "Visa", "distribution", "adjacent", 1, "A payments network that benefits from more transactions at little extra cost."),
            S("COST", "Costco", "distribution", "adjacent", 1, "Trusted retail that passes lower costs to members; hard for AI to replace."),
            S("PLD", "Prologis", "scarce", "adjacent", 1, "Logistics and warehouse real estate that automation still needs."),
            S("OKLO", "Oklo", "energy", "emerging", 3, "Pre-revenue small modular nuclear reactor developer."),
            S("SMR", "NuScale Power", "energy", "emerging", 3, "Small modular reactor designer; years from commercial output."),
            S("BE", "Bloom Energy", "energy", "emerging", 3, "Fuel cells increasingly sold as on-site power for data centers."),
            S("RXRX", "Recursion Pharmaceuticals", "science", "emerging", 3, "AI-driven drug discovery; unproven and cash-burning."),
            S("TEM", "Tempus AI", "science", "emerging", 3, "AI applied to clinical and genomic data."),
            S("ACN", "Accenture", "disrupted", "atrisk", 3, "Sells consulting and technology labor by the hour; also adapting by selling AI services."),
            S("CTSH", "Cognizant", "disrupted", "atrisk", 3, "IT services and outsourcing built on large teams of engineers."),
            S("EPAM", "EPAM Systems", "disrupted", "atrisk", 3, "Software engineering outsourcing."),
            S("GLOB", "Globant", "disrupted", "atrisk", 3, "Digital engineering services priced on headcount."),
            S("TTEC", "TTEC Holdings", "disrupted", "atrisk", 3, "Call-center outsourcing, a direct target for AI agents."),
            S("RHI", "Robert Half", "disrupted", "atrisk", 3, "Staffing for white-collar roles AI may reduce."),
            S("MAN", "ManpowerGroup", "disrupted", "atrisk", 3, "Global staffing; sensitive to both the cycle and automation."),
            S("CHGG", "Chegg", "disrupted", "atrisk", 3, "Homework help, already hit hard by free AI tutors: an example of how fast it can happen."),
        ],
        "etfs": [("SMH", "VanEck Semiconductor ETF"), ("BOTZ", "Global X Robotics & AI ETF"), ("GRID", "First Trust NASDAQ Clean Edge Smart Grid Infrastructure ETF")],
        "shortTerm": {
            "catalysts": ["Evidence that AI is replacing or speeding up routine knowledge work inside large companies",
                          "Power and grid investment announcements tied to data centers",
                          "Falling prices for AI usage widening what is worth automating"],
            "risks": ["Hype outrunning real productivity gains, followed by a sharp reset",
                      "Power, chips and permitting bottlenecks slowing the build-out",
                      "Political and regulatory backlash over jobs, safety and concentration"],
        },
        "longTerm": {
            "drivers": ["Machines making cognitive work, and later much physical work, far cheaper",
                        "Cheaper energy and faster science (medicine, materials) compounding the effect",
                        "Productivity gains that, if widely shared, raise living standards and create new kinds of demand and work"],
            "risks": ["Gains concentrating in a few owners, with weak demand if wages and employment fall faster than new work appears",
                      "Transition pain for displaced workers prompting heavy regulation or new taxes on capital",
                      "The technology plateauing short of the vision, leaving expensive infrastructure and unmet expectations"],
        },
        "watch": "Treat this as a scenario map, not a forecast. The infrastructure owners are the most direct bet, but they are also the most crowded. The disrupted names are shown for contrast, not as short ideas: many will adapt, and prices may already reflect the threat.",
        "impact": {
            "intro": "What follows is a way of thinking about the scenario, written by hand and dated. None of it is a prediction; the timing and the distribution of gains are the two things nobody knows.",
            "jobs": {
                "summary": "Past technology waves removed some jobs, created others and raised output, but each transition was uneven and slow for the people in the middle. AI is different in that it targets thinking tasks, not only physical ones, and it may move faster. The likeliest pattern in any version of the future is that tasks change before whole jobs vanish.",
                "exposed": ["Routine, screen-based work: data entry, basic customer support, first-draft writing, simple coding, back-office processing",
                            "Work sold by the hour with a standard output: outsourcing, entry-level analysis, translation, basic legal and accounting prep"],
                "resilient": ["Hands-on skilled trades and care work in unpredictable physical settings",
                              "Roles built on trust, accountability or presence: clinicians, teachers, managers, regulated professions",
                              "People who direct, check and combine AI tools, and those who own the scarce inputs"],
                "emerging": ["Roles to build, run, secure and audit AI systems and the power and data-center infrastructure under them",
                             "New products and services made affordable by cheap intelligence, which today's job titles don't capture"],
            },
            "markets": [
                {"title": "Costs fall faster than prices", "text": "Where AI cuts the cost of producing a service, profit margins can widen at first, until competition passes the savings on to customers. Early winners are the companies that pocket the gap."},
                {"title": "Scarce inputs reprice", "text": "When intelligence is cheap, what stays scarce becomes valuable: compute, electricity, certain materials, land near power and fiber, proprietary data, distribution and trusted brands."},
                {"title": "Winner-take-most tendencies", "text": "Scale in compute, data and distribution compounds. Markets may concentrate further, which helps leaders and raises regulatory and political risk."},
                {"title": "Prices and rates are unclear", "text": "Cheaper goods and services could push inflation down. A surge in investment, or in government spending to cushion workers, could push the other way. The path of interest rates would shape every valuation."},
                {"title": "Demand is the loop", "text": "Abundant output only pays off if people still have income to buy it. Whether gains are broadly shared, taxed or redistributed decides whether the abundance is a boom, a slump, or something new."},
            ],
            "winners": [
                {"who": "Owners of the scarce inputs", "why": "Compute and chips, power generation and grid equipment, and the minerals and real estate they depend on sell into demand that grows whoever wins downstream. Most direct, and most crowded."},
                {"who": "Distribution and trust", "why": "Networks, payments, marketplaces and trusted brands keep pricing power while their costs fall, and AI strengthens rather than replaces them."},
                {"who": "Science and health", "why": "If AI speeds discovery and cuts the cost of care, the winners are the companies with real products, data and regulatory approval, though this is a slower and riskier path."},
                {"who": "Labor-saving machines", "why": "Robotics and automation benefit as labor stays expensive relative to machines, with the long-term upside still unproven for general-purpose robots."},
                {"who": "Adaptable incumbents", "why": "Large companies that use AI to cut costs and keep their customers can gain from the shift, so even 'at risk' sectors contain survivors."},
            ],
            "scenarios": [
                {"name": "Broad abundance", "text": "AI and automation lift productivity widely, goods and services get cheaper, and new demand and jobs appear. Output and living standards rise.", "favours": "Infrastructure, energy, science and health, consumer-facing leaders, the whole market", "hurts": "Pure headcount-based services"},
                {"name": "Concentrated gains", "text": "Productivity rises but the benefits go mostly to the owners of compute, data and distribution while many workers lose out. Demand weakens and politics responds.", "favours": "A handful of platform and infrastructure owners, until regulation or taxes bite", "hurts": "Labor-intensive sectors, consumer discretionary, anything dependent on mid-income spending"},
                {"name": "Slower than hoped", "text": "Reliability, cost, power or regulation limit how fast AI is adopted; the build-out overshoots and expectations reset.", "favours": "Cash-rich incumbents, defensive businesses", "hurts": "Heavily valued infrastructure and speculative names that financed growth with debt or new shares"},
            ],
        },
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
