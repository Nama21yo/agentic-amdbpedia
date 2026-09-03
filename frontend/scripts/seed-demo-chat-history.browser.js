// Seeds realistic demo chat history into the browser's localStorage, for
// preparing a demo ahead of time rather than building history live on
// stage. This is a BROWSER console script, not a Node script -- it writes
// to `window.localStorage`, which only exists in the browser the app is
// actually open in.
//
// How to use:
//   1. Open the frontend (pnpm run dev --open, or wherever it's deployed)
//      in the browser you'll demo from.
//   2. Open DevTools (F12) -> Console.
//   3. Paste this entire file's contents and press Enter.
//   4. Refresh the page. The sidebar now shows ~9 sessions spread across
//      Today / Yesterday / Previous 7 days / Older -- exercising the
//      recency grouping, search, and status-badge states all at once.
//
// Every mapping/confidence/property value below is real, live-verified
// data from this project's own conversation history (rag/retrieval.py's
// real RRF scores, mcp_server/pipeline.py's real predicted mappings) --
// not fabricated placeholders. Every seeded pipeline turn that has
// mappings is given an already-resolved reviewStatus (approved/rejected/
// published): clicking Approve/Reject on a *live, still-pending* turn
// calls the real decideReview() against a real backend id, and a
// seeded-but-fake id would 404 -- so nothing here is left in a state
// where a click would hit that. Demo the live approve/reject flow with a
// fresh submission instead; this script is for populating *history*.
//
// Merges with whatever's already in localStorage rather than overwriting
// it -- safe to run on a browser that already has real sessions.

(function seedDemoChatHistory() {
	const STORAGE_KEY = 'amdbpedia:chat-sessions:v1';
	const now = Date.now();
	const HOUR = 3_600_000;
	const DAY = 24 * HOUR;

	function turnId() {
		return crypto.randomUUID();
	}

	// --- Real, verified pipeline results -------------------------------

	const gerdInfobox =
		'{{Infobox ግድብ\n| ስም = ታላቁ የኢትዮጵያ ሕዳሴ ግድብ\n| ስዕል = GERD 2.jpg\n| አገር = ኢትዮጵያ\n| ወንዝ = አባይ ወንዝ\n| ግንባታ_የተጀመረበት = መጋቢት ፳፬ ቀን ፪፲፻፫ ዓ.ም. (ኤፕሪል 2, 2011 እ.ኤ.አ.)\n| ከፍታ = 145 ሜትር\n| የውሃ_መጠን = 74 ቢሊዮን ኪዩቢክ ሜትር (አጠቃላይ አቅም)\n| የኤሌክትሪክ_ሀይል = 5,150 ሜጋ ዋት (MW)\n}}';

	/** @param {string} input @param {string} targetClass */
	function gerdNoMatchTurn(input, targetClass) {
		return {
			id: turnId(),
			kind: 'pipeline',
			input,
			targetClass,
			steps: [],
			// Live-verified: ስም/ስዕል/ከፍታ are already-published mappings
			// (filtered before prediction ever runs); አገር/ወንዝ/
			// ግንባታ_የተጀመረበት/የውሃ_መጠን/የኤሌክትሪክ_ሀይል have no confident retrieval
			// candidate in the corpus yet (a real corpus-coverage gap, not a
			// pipeline bug -- traced live to e.g. "አገር" vs the corpus's only
			// curated spelling "ሀገር").
			mappings: [],
			mappingWikitext: '',
			xmlRules: '',
			reviewItemId: null,
			running: false
		};
	}

	const riverTurn = {
		id: turnId(),
		kind: 'pipeline',
		input: '{{Infobox river\n| ስም = አባይ ወንዝ\n| ርዝመት = 6,650 ኪ.ሜ\n}}',
		targetClass: 'River',
		steps: [],
		mappings: [{ templateProperty: 'ርዝመት', ontologyProperty: 'length', confidence: 0.75 }],
		mappingWikitext:
			'{{TemplateMapping\n | mapToClass = River\n | mappings =\n  {{PropertyMapping | templateProperty = ርዝመት | ontologyProperty = length }}\n}}',
		xmlRules:
			'<TemplateMapping mapToClass="dbo:River">\n  <PropertyMapping>\n    <templateProperty>ርዝመት</templateProperty>\n    <ontologyProperty>length</ontologyProperty>\n  </PropertyMapping>\n</TemplateMapping>',
		reviewItemId: turnId(),
		reviewStatus: 'published',
		running: false
	};

	const castleTurn = {
		// Real transcript: literally approved live via the real backend
		// during this session (id babd69cd-eea7-4e96-8208-54849ab5c19f).
		id: turnId(),
		kind: 'pipeline',
		input: '{{Infobox castle\n| ርዝመት = 12 ኪ.ሜ\n}}',
		targetClass: 'Castle',
		steps: [],
		mappings: [{ templateProperty: 'ርዝመት', ontologyProperty: 'length', confidence: 0.75 }],
		mappingWikitext:
			'{{TemplateMapping\n | mapToClass = Castle\n | mappings =\n  {{PropertyMapping | templateProperty = ርዝመት | ontologyProperty = length }}\n}}',
		xmlRules:
			'<TemplateMapping mapToClass="dbo:Castle">\n  <PropertyMapping>\n    <templateProperty>ርዝመት</templateProperty>\n    <ontologyProperty>length</ontologyProperty>\n  </PropertyMapping>\n</TemplateMapping>',
		reviewItemId: 'babd69cd-eea7-4e96-8208-54849ab5c19f',
		reviewStatus: 'approved',
		running: false
	};

	const damTurn = {
		id: turnId(),
		kind: 'pipeline',
		input: '{{Infobox dam\n| ስም = ደደሳ ግድብ\n| የተከፈተበት_ቀን = 2018\n}}',
		targetClass: 'Dam',
		steps: [],
		mappings: [
			{ templateProperty: 'የተከፈተበት_ቀን', ontologyProperty: 'openingDate', confidence: 1.0 }
		],
		mappingWikitext:
			'{{TemplateMapping\n | mapToClass = Dam\n | mappings =\n  {{PropertyMapping | templateProperty = የተከፈተበት_ቀን | ontologyProperty = openingDate }}\n}}',
		xmlRules:
			'<TemplateMapping mapToClass="dbo:Dam">\n  <PropertyMapping>\n    <templateProperty>የተከፈተበት_ቀን</templateProperty>\n    <ontologyProperty>openingDate</ontologyProperty>\n  </PropertyMapping>\n</TemplateMapping>',
		reviewItemId: turnId(),
		reviewStatus: 'rejected',
		running: false
	};

	const mountainTurn = {
		id: turnId(),
		kind: 'pipeline',
		input: '{{Infobox mountain\n| ርዝመት = 8 ኪ.ሜ\n}}',
		targetClass: 'Mountain',
		steps: [],
		mappings: [{ templateProperty: 'ርዝመት', ontologyProperty: 'length', confidence: 0.75 }],
		mappingWikitext:
			'{{TemplateMapping\n | mapToClass = Mountain\n | mappings =\n  {{PropertyMapping | templateProperty = ርዝመት | ontologyProperty = length }}\n}}',
		xmlRules:
			'<TemplateMapping mapToClass="dbo:Mountain">\n  <PropertyMapping>\n    <templateProperty>ርዝመት</templateProperty>\n    <ontologyProperty>length</ontologyProperty>\n  </PropertyMapping>\n</TemplateMapping>',
		reviewItemId: turnId(),
		reviewStatus: 'approved',
		running: false
	};

	/** @param {string} input @param {import('../src/lib/types').MappingCandidate[] | null} matches @param {boolean} noMatch */
	function answerTurn(input, matches, noMatch) {
		return { id: turnId(), kind: 'answer', input, matches, noMatch, running: false };
	}

	const professionMatch = [
		{
			property: 'profession',
			class: 'Person',
			score: 1.0,
			payload: {
				curie: 'dbo:profession',
				uri: 'http://dbpedia.org/ontology/profession',
				label: 'profession',
				property_type: 'ObjectProperty',
				amharic_aliases: ['ሙያ'],
				english_aliases: []
			}
		}
	];

	const lengthMatches = [
		{
			property: 'length',
			class: 'Bridge',
			score: 0.75,
			payload: {
				curie: 'dbo:length',
				uri: 'http://dbpedia.org/ontology/length',
				label: 'length',
				property_type: 'DatatypeProperty',
				amharic_aliases: ['ርዝመት', 'የድልድይ_ርዝመት', 'የግድብ_ርዝመት', 'የወንዝ_ርዝመት'],
				english_aliases: []
			}
		},
		{
			property: 'penisLength',
			class: 'Person',
			score: 0.5,
			payload: {
				curie: 'dbo:penisLength',
				uri: 'http://dbpedia.org/ontology/penisLength',
				label: 'penis length',
				property_type: 'DatatypeProperty',
				amharic_aliases: [],
				english_aliases: []
			}
		},
		{
			property: 'lineLength',
			class: 'RouteOfTransportation',
			score: 0.3333333333333333,
			payload: {
				curie: 'dbo:lineLength',
				uri: 'http://dbpedia.org/ontology/lineLength',
				label: 'line length',
				property_type: 'DatatypeProperty',
				amharic_aliases: [],
				english_aliases: []
			}
		}
	];

	const nameMatches = [
		{
			property: 'name',
			class: '',
			score: 0.5555555555555556,
			payload: {
				curie: 'dbo:name',
				uri: 'http://dbpedia.org/ontology/name',
				label: 'name',
				property_type: 'DatatypeProperty',
				amharic_aliases: ['ስም', 'ሙሉ_ስም', 'ኗሪ_ስም', 'ርዕስ', 'ርዕስ_በሌላ_ቋንቋ'],
				english_aliases: []
			}
		},
		{
			property: 'sameName',
			class: 'Settlement',
			score: 0.5,
			payload: {
				curie: 'dbo:sameName',
				uri: 'http://dbpedia.org/ontology/sameName',
				label: 'same name',
				property_type: 'DatatypeProperty',
				amharic_aliases: [],
				english_aliases: []
			}
		},
		{
			property: 'foaf:surname',
			class: '',
			score: 0.3333333333333333,
			payload: {
				curie: 'foaf:surname',
				uri: 'http://xmlns.com/foaf/0.1/surname',
				label: 'surname',
				property_type: 'DatatypeProperty',
				amharic_aliases: [],
				english_aliases: []
			}
		}
	];

	// --- Sessions, oldest info last so the array ends up newest-first --

	function session(title, turns, updatedAt) {
		return { id: crypto.randomUUID(), title, turns, updatedAt };
	}

	const demoSessions = [
		session('Extract GERD dam infobox', [gerdNoMatchTurn(gerdInfobox, 'Dam')], now - 25 * 60_000),
		session(
			'GERD dam, from its Wikipedia link',
			[gerdNoMatchTurn('https://am.wikipedia.org/wiki/ታላቁ_የኢትዮጵያ_ሕዳሴ_ግድብ', 'Dam')],
			now - 2 * HOUR
		),
		session(
			'Quick field lookups',
			[
				answerTurn('ሙያ', professionMatch, false),
				answerTurn('ርዝመት', lengthMatches, false),
				answerTurn('ዜግነት', null, true)
			],
			now - 4 * HOUR
		),
		session('Infobox river — published', [riverTurn], now - 26 * HOUR),
		session('Infobox mountain — approved', [mountainTurn], now - 30 * HOUR),
		session('Infobox castle — approved', [castleTurn], now - 3 * DAY),
		session(
			'Random gibberish input',
			[answerTurn('asdkj random gibberish blah blah', null, true)],
			now - 5 * DAY
		),
		session('Infobox dam — rejected', [damTurn], now - 20 * DAY),
		session('Ask what a field maps to', [answerTurn('ስም', nameMatches, false)], now - 45 * DAY)
	];

	// --- Merge with whatever's already there, newest-first -------------

	let existing = [];
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		existing = raw ? JSON.parse(raw) : [];
		if (!Array.isArray(existing)) existing = [];
	} catch (err) {
		console.warn('Could not read existing chat history, starting fresh:', err);
	}

	const merged = [...existing, ...demoSessions].sort((a, b) => b.updatedAt - a.updatedAt);
	localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));

	console.log(
		`Seeded ${demoSessions.length} demo chat sessions (${existing.length} pre-existing kept). Refresh the page.`
	);
})();
