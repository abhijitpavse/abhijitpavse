import requests

USERNAME = "abhijitpavse"

API = f"https://api.github.com/users/{USERNAME}/repos?sort=updated&per_page=100"

repos = requests.get(API).json()

ignore = {
    USERNAME.lower()
}

repos = [
    r for r in repos
    if not r["fork"]
    and r["name"].lower() not in ignore
]

repos = repos[:3]

markdown = ""

for repo in repos:

    language = repo["language"] if repo["language"] else "Not specified"

    desc = repo["description"] if repo["description"] else "No description"

    markdown += f"""
### 📦 [{repo['name']}]({repo['html_url']})

{desc}

**Language:** `{language}`

⭐ {repo['stargazers_count']} | 🍴 {repo['forks_count']}

---
"""

with open("README.md","r",encoding="utf8") as f:
    readme = f.read()

start="<!--START_SECTION:repos-->"
end="<!--END_SECTION:repos-->"

new_readme=readme.split(start)[0]+start+"\n"+markdown+"\n"+end+readme.split(end)[1]

with open("README.md","w",encoding="utf8") as f:
    f.write(new_readme)
