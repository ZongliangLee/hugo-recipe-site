---
title: "食譜列表"
---

## 所有食譜

{{ range where .Site.Pages "Section" "recipes" }}
  * [{{ .Title }}]({{ .RelPermalink }})
{{ end }}