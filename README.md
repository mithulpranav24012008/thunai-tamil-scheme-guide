# Thunai — Tamil Scheme Guide

A Strands Agents SDK agent that helps people in Tamil Nadu and India discover and understand government health, medical-support, and education schemes. Its defining feature is natural, respectful Tamil conversation.

## What it does

- The user explains what they need in Tamil or English.
- Thunai understands the situation, asks only the necessary follow-up questions (one at a time), and suggests relevant Central, Tamil Nadu, or other verified India-wide schemes.
- For each scheme, it explains the benefit, eligibility, jurisdiction, likely documents, application steps, official link, and source date — in the user's preferred language.
- It never invents schemes, amounts, eligibility rules, or links. Unverifiable details are flagged and the user is directed to the official source.
- Medical emergencies are detected and handed off immediately — Thunai never diagnoses or prescribes.

## Setup

### Prerequisites

- Python 3.12
- AWS credentials with access to Amazon Bedrock in `us-east-1`
- Amazon Nova model access enabled in the Bedrock console (or set `SHIP_MODEL` to another Bedrock model)

### Install

```bash
# If you have the strands-ship power installed:
~/.strands-ship/bin/ss init    # already done if you ran setup

# Or without the power — create a venv and install:
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### AWS / Bedrock requirements

Thunai uses Amazon Bedrock for the planner, critic, and evaluation judge. The default model is `us.amazon.nova-2-lite-v1:0` in `us-east-1`.

```bash
# Set up AWS credentials (profile-based):
aws login --region us-east-1 --profile <your-profile>
export AWS_PROFILE=<your-profile>
export AWS_REGION=us-east-1
export SHIP_MODEL=us.amazon.nova-2-lite-v1:0  # optional, this is the default

# Verify access:
~/.strands-ship/bin/ss bedrock
```

Credentials are read from environment variables or the AWS CLI profile. No keys are stored in source code.

## How to run

### One-shot mode

```bash
# English
python -m agent.app "I need health insurance for hospital treatment"

# Tamil
python -m agent.app "எனக்கு சுகாதார காப்பீடு தேவை"

# JSON output
python -m agent.app "I need a scholarship for my SC child" --json

# Or through the ship kit:
~/.strands-ship/bin/ss run "I need health insurance for hospital treatment"
```

### Interactive chat mode

```bash
python -m agent.app --chat
```

This opens a conversation where you can ask questions in Tamil or English, and Thunai asks follow-up questions one at a time to narrow your eligibility.

### Speech input (--voice and --audio)

Thunai can transcribe spoken Tamil, Tanglish (Tamil in English script), and Indian English using Amazon Transcribe, then run the transcript through the same agent path.

```bash
# Transcribe an audio file and answer (testable path, no microphone needed)
python -m agent.app --audio recording.wav

# Transcribe with Indian English
python -m agent.app --audio recording.wav --stt-lang en-IN

# Interactive voice chat (requires microphone)
python -m agent.app --chat --voice
```

Install the speech dependencies:

```bash
pip install amazon-transcribe==0.6.4          # for --audio and --voice
pip install sounddevice==0.5.6 numpy          # for --voice only (macOS: also run brew install portaudio)
```

**Supported languages** (verified from AWS docs, 2026-11-04):
- Tamil (`ta-IN`): batch and streaming — [Transcribe supported languages](https://docs.aws.amazon.com/transcribe/latest/dg/supported-languages.html)
- Indian English (`en-IN`): batch and streaming — [announced 2019](https://aws.amazon.com/about-aws/whats-new/2019/05/amazon-transcribe-supports-hindi-indian-accented-english/)

**Not supported** (checked and confirmed):
- Amazon Nova 2 Sonic: no Tamil — [language support](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-language-support.html)
- Amazon Polly: no Tamil voice
- Strands bidi voice extras: built on Nova Sonic, so no Tamil

**Text-to-speech (spoken replies) is out of scope** — no AWS service has a Tamil voice. The agent shows the transcript and the text answer on screen.

**Safety with speech**: an emergency spoken in Tamil, Tanglish, or English still triggers the red-flag hook and hands off to 108 immediately. If the transcript is low-confidence, the agent asks the user to repeat — unless it contains red-flag words, in which case it hands off anyway (a missed emergency is worse than a false alarm). Audio is never stored; temporary files are deleted after transcription.

## Examples

### Tamil — health insurance

```
You: எனக்கு சுகாதார காப்பீடு தேவை, மருத்துவமனையில் சிகிச்சை எடுக்க வேணும்

துணை: உங்கள் தேவை புரிகிறது. மருத்துவமனை சிகிச்சைக்கு அரசு திட்டங்கள் உண்டு.
  ── Ayushman Bharat PM-JAY (Central)
     பயன்: ஆண்டுக்கு 5 லட்சம் ரூபாய் வரை இலவச மருத்துவம்...
     Link: https://pmjay.gov.in/
```

### English — education scholarship

```
You: I'm an SC student in class 10, are there any scholarships for me?

Thunai: There are central government scholarships for SC students. Here's what may fit:
  ── Pre-Matric Scholarship for SC Students (Central)
     Benefit: Scholarship for SC students in classes IX and X...
     Link: https://scholarships.gov.in/
```

### Emergency handoff

```
You: I'm having chest pain and can't breathe

Thunai: This sounds like a medical emergency... Please call 108 for an ambulance
right now, or go to the nearest hospital. For mental health support, call KIRAN
at 1800-599-0199 (free, 24/7) or Tele-MANAS at 14416.
```

## Data-source approach

Thunai uses a small, clearly labelled verified dataset of government schemes (`agent/data/guidance.json`). Each scheme has:
- An official source URL and the date it was last checked
- Name, jurisdiction, benefit, eligibility, exclusions, documents, application steps

This is **not** a complete catalogue. It covers 10 well-known schemes across health and education. The agent tells users when information is missing or needs verification, and directs them to the official source.

To add or update schemes, edit `agent/data/guidance.json` and add a source with a URL and date. Re-run `ss measure` after any change.

## Limitations

- **Not a complete catalogue**: Only 10 schemes are included. The agent will say when it cannot find a relevant scheme.
- **Information may be outdated**: Scheme details change. Always verify with the official scheme administrator before applying.
- **Not a doctor, lawyer, or emergency service**: Thunai is a scheme-navigation assistant. It does not diagnose, prescribe, or recommend treatment. For medical emergencies, call 108.
- **No guarantee of eligibility**: Thunai presents schemes worth checking. Final eligibility must be confirmed with the official scheme administrator.
- **Tamil accuracy**: Tamil text from the model may have errors. Emergency text, handoff messages, and key safety phrases are fixed in code, but general Tamil responses should be reviewed by a fluent reader.
- **Emergency detection is a word list, not understanding**: `agent/safety.py` catches written and spoken Tamil, Tanglish (Tamil typed in English letters) and common English phrasings, and is tested in `tests/test_safety.py`. A phrasing nobody has added yet will be missed. Add it there, with a test, whenever a real user writes one.
- **Tanglish replies come back in Tamil script**: a question typed in Tanglish is answered in Tamil, which some readers may find harder than Tanglish.

## Evaluation

The safety and language checks run without AWS:

```bash
python -m unittest discover tests
```


Thunai is measured against a single-prompt baseline on 40 labelled cases covering:
- Tamil, including Tanglish (21 cases), English (19 cases)
- Tamil-English code-switching
- Ambiguous needs
- Missing eligibility details
- Sensitive information (Aadhaar, bank details)
- Stale or unverifiable scheme claims
- Education (scholarships, bus pass)
- Health (insurance, maternity, disability, mental health)
- Emergency medical messages (14 cases, including spoken Tamil and Tanglish)
- Requests for diagnosis or treatment advice (2 care cases)

```bash
# Review cases:
~/.strands-ship/bin/ss cases check
~/.strands-ship/bin/ss cases show

# Sign off (after reviewing each label):
~/.strands-ship/bin/ss cases approve --by "Your Name"

# Run the measurement:
~/.strands-ship/bin/ss measure
```

The measurement gate requires 100% emergency recall, 0 unsafe plans, 100% threshold accuracy, ≥95% citation faithfulness, ≥90% completeness, and goal success beating the baseline.

### Results (measured 2026-11-04, Nova 2 Lite, 40 cases) — gate passed

| Metric | Thunai | Single-prompt baseline |
|---|---|---|
| Emergency cases escalated to 108 / KIRAN | 100% | 86% |
| Plans with unsafe advice | 0 | 3 |
| Key scheme facts present (must_include) | 100% | 92% |
| Citations that exist in the guidance | 100% | 100% |
| Plan fields complete, right language | 100% | 68% |
| Goal success (Strands Evals judge, 0-1) | 1.0 | 0.784 |
| Latency p50 | 6193 ms | 4269 ms |

Agent: 8 normal answers, 16 emergency handoffs, 16 recovered from verified records, 0 "please rephrase", 0 crashes. Thunai beats the baseline on every metric. The gate passed all 11 checks.

## Important note

**Eligibility must be confirmed with official scheme administrators.** Thunai is a navigation assistant, not an authority on scheme eligibility. Always verify with the official portal or office before applying.
