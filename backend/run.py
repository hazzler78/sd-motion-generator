import uvicorn
import os
import sys

# Lägg till src-katalogen i Python-sökvägen
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
sys.path.append(src_dir)

if __name__ == "__main__":
    # Kör FastAPI-servern med uvicorn
    uvicorn.run(
        "politik.main:app",  # Uppdaterad sökväg
        host="0.0.0.0",  # Tillåt extern åtkomst
        port=8000,       # Standard port
        reload=True      # Automatisk omladdning vid kodändringar
    ) 