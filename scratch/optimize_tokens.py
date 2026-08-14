import os
import re

def optimize():
    file_path = os.path.join("src", "skills", "analysis.py")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Replace rationale in JSON templates
    replacements = [
        ('"rationale": "Short analysis of indicators, support levels, and momentum."', '"rationale": "Brief summary (max 1 sentence)."'),
        ('"rationale": "Brief critique of valuation, debt burden, and growth profile."', '"rationale": "Brief summary (max 1 sentence)."'),
        ('"rationale": "Brief summary of news landscape."', '"rationale": "Brief summary (max 1 sentence)."'),
        ('"rationale": "Critique of R&D reinvestment efficiency, revenue growth momentum, and long-term scaling outlook."', '"rationale": "Brief summary (max 1 sentence)."'),
        ('"rationale": "Brief macro rationale."', '"rationale": "Brief summary (max 1 sentence)."'),
        ('"rationale": "Brief reasoning for sector strength."', '"rationale": "Brief summary (max 1 sentence)."'),
        ('"rationale": "Brief qualitative evaluation."', '"rationale": "Brief summary (max 1 sentence)."'),
        ('"rationale": "Brief historical comparison."', '"rationale": "Brief summary (max 1 sentence)."'),
        ('"rationale": "Brief explanation"', '"rationale": "Brief summary (max 1 sentence)."')
    ]
    
    for old, new in replacements:
        content = content.replace(old, new)
        
    # Replace llm.call(...) with max_tokens=250
    # Match: self.llm.call(prompt, system_prompt=...) but not if it already has max_tokens
    # A simple regex: self\.llm\.call\((.*?)\) -> check if max_tokens is in there, if not append it
    
    def repl_llm_call(match):
        args = match.group(1)
        if "max_tokens" not in args:
            return f"self.llm.call({args}, max_tokens=250)"
        return match.group(0)

    content = re.sub(r'self\.llm\.call\((.*?)\)', repl_llm_call, content)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    print("Done optimizing analysis.py")

if __name__ == "__main__":
    optimize()
