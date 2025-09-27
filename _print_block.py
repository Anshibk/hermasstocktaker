from pathlib import Path
text = Path("app/static/js/app.js").read_text()
start = text.index("      tbody.innerHTML=rows.map((line,idx)=>{")
end = text.index("      }).join('');", start) + len("      }).join('');")
print(repr(text[start:end]))
