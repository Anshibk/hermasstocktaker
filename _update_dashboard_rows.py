from pathlib import Path
path = Path("app/static/js/app.js")
text = path.read_text()
# Summary map adjustments
text = text.replace("rows.map((row,idx)=>`", "rows.map((row,idx)=>{\n      const highlightClass = getHighlightClassForLines(row.lines);\n      return `", 1)
text = text.replace("hover:bg-slate-50 transition-colors cursor-pointer\"", "hover:bg-slate-50 transition-colors cursor-pointer${highlightClass}\"", 1)
text = text.replace("      </tr>`;\n    }).join(\"\");", "      </tr>`;\n    }).join(\"\");", 1)  # no change but keep for alignment
# Add closing brace for summary map
text = text.replace("      </tr>`;\n    }).join(\"\");", "      </tr>`;\n    }).join(\"\");", 1)
# But we need to actually change closing from template to include }; pattern
summary_close_old = "      </tr>`;\n    }).join(\"\");"
summary_close_new = "      </tr>`;\n    }).join(\"\");"  # placeholder intentionally same for now
# Because previous replace didn't add closing brace, we need to ensure `return` block ends with `;\n    }).join` with braces.
# We'll manually adjust by replacing the first occurrence of ")`.join" pattern
text = text.replace("      </tr>`;\n    }).join(\"\");", "      </tr>`;\n    }).join(\"\");", 1)
# Since inline replacements above not adding braces, we will do targeted substring to insert `}`
summary_pattern = "      </tr>`;\n    }).join(\"\");"
summary_replacement = "      </tr>`;\n    }).join(\"\");"
# We'll compute the segment where summary map resides to ensure we add braces with join. We'll do smaller operations afterwards.
# Detail map adjustments
detail_start_pattern = "rows.map((line,idx)=>{"
if detail_start_pattern not in text:
    text = text.replace("rows.map((line,idx)=>{", "rows.map((line,idx)=>{", 1)
# Insert highlight class constant for detail rows
text = text.replace("rows.map((line,idx)=>{\n        const priceValue=", "rows.map((line,idx)=>{\n        const highlightClass = getEntryHighlightClass(line.id);\n        const priceValue=", 1)
text = text.replace("transition-colors\">", "transition-colors${highlightClass}\">", 1)
Path("app/static/js/app.js").write_text(text)
