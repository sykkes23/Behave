# BEHAVE: AI Behavior Test Lab

Does your AI actually get better when you change it?

Behave is an AI evaluation and regression testing laboratory. It acts as a safety inspector for your AI, running it through hundreds of simulated conversations to determine if your latest prompt changes or model updates introduced behavioral regressions, safety failures, or cost explosions.

The best way to understand Behave is to try it yourself.

## Zero-Experience Demo

You don't need API keys, Python experience, or configuration to try Behave. 
We've included a built-in demo agent that simulates a "V1" and "V2" AI so you can see exactly how the laboratory evaluates behavior, safety, and reliability.

### How to Launch

**On Windows:**
Simply double-click `Start_Behave.bat`

**On Mac / Linux:**
Open a terminal and run:
```bash
./Start_Behave.sh
```
*(Note: You need Python 3 installed on your system. No external dependencies are required.)*

### What Happens Next?
1. Behave will start a local server and automatically open a dashboard in your browser (`http://127.0.0.1:5000`).
2. Click **TRY DEMO**.
3. Select **Demo Agent (Built-in)** and watch Behave run 8 parallel simulated conversations.
4. Review the results! You will see exactly how Agent V2 improved over Agent V1, including safety checks, behavioral scoring, and the final deployment recommendation.

## Testing Your Own AI

Once you understand the demo, you can use Behave to test your own AI endpoints!

1. From the Behave Dashboard, select **TEST MY AI** (or click one of the external endpoint options).
2. Enter your candidate and baseline API endpoints (e.g., `http://localhost:11434/v1/chat/completions` for Ollama).
3. Select a test size (Quick, Standard, Full).
4. Run the test and get a statistically sound evaluation of your AI.

## Technical Details

Behave operates locally and does not send your data to the cloud. The laboratory contains:
- **Stateful Evaluator:** Evaluates conversations across multiple turns.
- **Decision Engine:** Translates statistical significance (Cohen's d, p-values) into clear DEPLOY/BLOCKED recommendations.
- **Measurement Integrity:** Tracks LLM judge reliability and human overrides.
- **Failure Taxonomy:** Automatically categorizes regressions (e.g., `unsafe_physical_action`, `premature_conclusion`).

*Welcome to the lab.*
