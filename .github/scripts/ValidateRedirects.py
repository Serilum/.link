# -*- coding: utf-8 -*-
#!/usr/bin/env python
from urllib.parse import urlparse
import os
import re
import sys

REDIRECTS_FILE = "_redirects"
ALLOWED_STATUSES = ["301", "302", "303", "307", "308"]
MAX_STATIC_RULES = 2000
MAX_DYNAMIC_RULES = 100

fprefix = " [Validate Redirects] "
isGitHubAction = os.environ.get("GITHUB_ACTIONS", "") == "true"


def isDynamic(source):
	return "*" in source or re.search(r":[A-Za-z]", source) is not None


def placeholdersIn(path):
	return re.findall(r":[A-Za-z]\w*", path)


def validateSource(source):
	problems = []
	if not source.startswith("/"):
		problems.append("'" + source + "' must start with /")

	if len(source) > 1 and source.endswith("/"):
		problems.append("'" + source + "' ends with /, a link with a trailing slash is easy to miss")

	return problems


def validateDestination(source, destination):
	parsed = urlparse(destination)
	if parsed.scheme == "" or parsed.netloc == "":
		return ["'" + destination + "' is not a full URL (expected https://...)"]

	problems = []
	if parsed.scheme != "https":
		problems.append("'" + destination + "' should use https://")

	sourcePlaceholders = placeholdersIn(source)
	for placeholder in placeholdersIn(parsed.path + parsed.query):
		if placeholder == ":splat":
			isDefined = "*" in source
		else:
			isDefined = placeholder in sourcePlaceholders

		if not isDefined:
			problems.append("destination uses " + placeholder + " but the source '" + source + "' does not define it")

	return problems


def validateStatus(status):
	if status is not None and status not in ALLOWED_STATUSES:
		return ["status '" + status + "' must be one of " + ", ".join(ALLOWED_STATUSES)]

	return []


def printProblem(filePath, lineNumber, problem):
	if isGitHubAction:
		location = ",line=" + str(lineNumber) if lineNumber > 0 else ""
		print("::error file=" + filePath + location + "::" + problem)
	else:
		location = "Line " + str(lineNumber) + ": " if lineNumber > 0 else ""
		print(fprefix + location + problem)


def main(filePath):
	print("\n" + fprefix + "Validating " + filePath + ".")

	with open(filePath, "r", encoding="utf-8") as f:
		lines = f.read().splitlines()

	problems = []
	firstLineBySource = {}
	firstDynamicLine = None
	staticCount = 0
	dynamicCount = 0

	for index, rawLine in enumerate(lines):
		lineNumber = index + 1
		line = rawLine.strip()
		if line == "" or line.startswith("#"):
			continue

		fields = line.split()
		if len(fields) < 2 or len(fields) > 3:
			problems.append((lineNumber, "expected '/link https://destination 302', got " + str(len(fields)) + " field(s)"))
			continue

		source = fields[0]
		destination = fields[1]
		status = fields[2] if len(fields) == 3 else None

		lineProblems = validateSource(source) + validateDestination(source, destination) + validateStatus(status)
		for problem in lineProblems:
			problems.append((lineNumber, problem))

		if source in firstLineBySource:
			problems.append((lineNumber, "'" + source + "' is already defined on line " + str(firstLineBySource[source])))
		else:
			firstLineBySource[source] = lineNumber

		if isDynamic(source):
			dynamicCount += 1
			if firstDynamicLine is None:
				firstDynamicLine = lineNumber
		else:
			staticCount += 1
			if firstDynamicLine is not None:
				problems.append((lineNumber, "'" + source + "' is below the catch-all on line " + str(firstDynamicLine) + ", so it never matches. Move it above"))

	if staticCount > MAX_STATIC_RULES:
		problems.append((0, str(staticCount) + " links, Cloudflare allows " + str(MAX_STATIC_RULES)))

	if dynamicCount > MAX_DYNAMIC_RULES:
		problems.append((0, str(dynamicCount) + " catch-all rules, Cloudflare allows " + str(MAX_DYNAMIC_RULES)))

	for lineNumber, problem in problems:
		printProblem(filePath, lineNumber, problem)

	summary = str(staticCount) + " link(s) and " + str(dynamicCount) + " catch-all rule(s)"
	if len(problems) > 0:
		print(fprefix + "Found " + str(len(problems)) + " problem(s) in " + summary + ".")
		sys.exit(1)

	print(fprefix + "No problems found in " + summary + ".")
	return


if __name__ == "__main__":
	main(sys.argv[1] if len(sys.argv) > 1 else REDIRECTS_FILE)
