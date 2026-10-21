import redirects from "../_redirects";

const untrackedpaths = ["/favicon.ico", "/robots.txt"];
const activelinks = getActiveLinks(redirects);
const botuseragents = /bot|crawl|spider|slurp|preview|embed|facebookexternalhit|whatsapp|curl|wget|python|java\/|go-http|okhttp|axios|node-fetch|headless/i;

export default {
	async fetch(request, env, ctx) {
		let url = new URL(request.url);
		if (url.hostname !== env.LINK_HOSTNAME) {
			return new Response("Not found", { status: 404 });
		}

		if (isTrackable(request, url)) {
			ctx.waitUntil(sendPageview(request, url, env));
		}

		return fetch(request, { redirect: "manual" });
	}
};

function isTrackable(request, url) {
	if (request.method !== "GET") {
		return false;
	}

	if (untrackedpaths.includes(url.pathname) || !activelinks.has(url.pathname)) {
		return false;
	}

	let useragent = request.headers.get("user-agent") || "";
	if (useragent === "" || botuseragents.test(useragent)) {
		return false;
	}

	return true;
}

async function sendPageview(request, url, env) {
	let headers = request.headers;
	let useragent = headers.get("user-agent");

	let payload = removeEmptyValues({
		website: env.UM_WEBSITE_ID,
		hostname: url.hostname,
		url: url.pathname,
		referrer: headers.get("referer"),
		language: getFirstLanguage(headers.get("accept-language")),
		ip: headers.get("cf-connecting-ip"),
		userAgent: useragent
	});

	try {
		let response = await fetch(env.UM_SEND_URL, {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				"User-Agent": useragent
			},
			body: JSON.stringify({ type: "event", payload: payload })
		});

		if (!response.ok) {
			console.log("Umami returned " + response.status + " for " + url.pathname);
		}
	} catch (error) {
		console.log("Could not send the pageview for " + url.pathname + ": " + error);
	}
}

function getActiveLinks(redirectstext) {
	let links = new Set();
	for (let line of redirectstext.split("\n")) {
		let source = line.trim().split(/\s+/)[0];
		if (!source || !source.startsWith("/")) {
			continue;
		}

		let isdynamic = source.includes("*") || /:[A-Za-z]/.test(source);
		if (!isdynamic) {
			links.add(source);
		}
	}

	return links;
}

function getFirstLanguage(acceptlanguage) {
	if (!acceptlanguage) {
		return null;
	}

	return acceptlanguage.split(",")[0].split(";")[0].trim();
}

function removeEmptyValues(object) {
	for (let [key, value] of Object.entries(object)) {
		if (!value) {
			delete object[key];
		}
	}

	return object;
}
