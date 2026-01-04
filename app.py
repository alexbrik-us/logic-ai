import streamlit as st
import clingo
from google import genai
from google.genai import types

# --- Configuration ---
# Get API Key from secrets (for deployment) or local testing
API_KEY = st.secrets.get("GOOGLE_API_KEY", "YOUR_API_KEY_HERE")

def get_gemini_client():
    if not API_KEY or "YOUR_API" in API_KEY:
        st.error("🚨 API Key is missing. Please check your Streamlit secrets.")
        return None
    return genai.Client(api_key=API_KEY)

def translate_to_asp(client, text_query):
    """
    Step 1: Ask Gemini to convert natural language to Clingo/ASP rules.
    """
    prompt = f"""
    You are an expert in Answer Set Programming (ASP) using Clingo syntax.
    Convert the following logic puzzle/description into a valid Clingo ASP program.
    
    User Query: "{text_query}"
    
    Requirements:
    - Output ONLY the raw ASP code inside a code block.
    - Do not add markdown explanations outside the code block.
    - Use standard clingo syntax (rules, facts, constraints).
    - If the problem asks to find a solution, ensure you produce answer sets (models).
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt]
        )
        # Extract code from Markdown code blocks (```asp or ```)
        text = response.text
        if "```" in text:
            # simple parsing to get content between backticks
            return text.split("```")[1].replace("asp", "").replace("clingo", "").strip()
        return text.strip() # Fallback if no code blocks
    except Exception as e:
        st.error(f"Translation Error: {e}")
        return None

def run_clingo(asp_code):
    """
    Step 2: Run the generated code through the Clingo solver.
    """
    models = []
    
    def on_model(m):
        # Convert the model (list of atoms) to a string representation
        models.append(str(m))

    ctl = clingo.Control(["0"])
    
    try:
        ctl.add("base", [], asp_code)
        ctl.ground([("base", [])])
        result = ctl.solve(on_model=on_model)
        
        if result.satisfiable:
            return models
        else:
            return ["UNSATISFIABLE (No solution found)"]
    except Exception as e:
        return [f"Clingo Error: {e}"]

def interpret_solution(client, original_query, asp_code, clingo_output):
    """
    Step 3: Ask Gemini to explain the solver's output to the user.
    """
    prompt = f"""
    I have a logic puzzle.
    
    1. The User's Question: "{original_query}"
    2. The Logic Rules (ASP): 
    {asp_code}
    3. The Solver's Output (Models):
    {clingo_output}
    
    Based on the Solver's Output, please give a clear, natural language answer to the user's question. 
    Explain which solution was found.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt]
        )
        return response.text
    except Exception as e:
        return f"Interpretation Error: {e}"

# --- UI Layout ---
st.set_page_config(page_title="Neuro-Symbolic Logic Solver", page_icon="🧠")

st.title("Logic Solver (ASP + Gemini)")
st.markdown("This app uses **Gemini** to write logic rules and **Clingo** to solve them rigorously.")

# Input
query = st.text_area("Describe your logic puzzle:", height=150,
    placeholder="e.g., In a box I have a blue dinosaur, a red pen and a green ball. The dinosaur is not next to the pen. What is in the middle?")
# Another example:
# 4 people are sitting at a round table: Alex, Becca, Clancy and David. Alex is sitting across from Clancy.
# David is sitting to the right of Alex. Who is sitting to the left of Clancy?

if st.button("Solve Logic"):
    if not query:
        st.warning("Please enter a question.")
    else:
        client = get_gemini_client()
        if client:
            # 1. Translate
            with st.status("Thinking... (Step 1: Translating to Logic)", expanded=True) as status:
                st.write("Generating Clingo/ASP rules...")
                asp_code = translate_to_asp(client, query)
                st.code(asp_code, language="prolog")
                
                # 2. Solve
                status.update(label="Reasoning... (Step 2: Running Clingo Solver)", state="running")
                st.write("Solving logic program...")
                models = run_clingo(asp_code)
                st.write(f"Found {len(models)} Model(s):")
                st.json(models)
                
                # 3. Interpret
                status.update(label="Synthesizing... (Step 3: Final Answer)", state="running")
                final_answer = interpret_solution(client, query, asp_code, models)
                status.update(label="Complete!", state="complete", expanded=False)
            
            # Final Output
            st.divider()
            st.subheader("💡 Answer")
            st.markdown(final_answer)