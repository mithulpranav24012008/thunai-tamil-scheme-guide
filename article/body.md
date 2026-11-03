# Thunai — Tamil Scheme Guide

*Helping people in Tamil Nadu and India discover government health and education schemes, in their own language.*

## The problem

India has hundreds of government schemes for health insurance, maternity care, scholarships, disability support, and mental health. But the people who need them most often miss out. The information is scattered across portals, eligibility rules are complex, and much of it is in English or bureaucratic Hindi — not in the Tamil that millions of people in Tamil Nadu actually speak.

A pregnant woman in a village near Madurai may not know about the Dr. Muthulakshmi Reddy Maternity Benefit Scheme. A first-generation college student from a Scheduled Caste family may never discover the Pre-Matric Scholarship that could keep them in school. A person with a disability may not know a pension exists for them. The gap between the schemes that exist and the people they are meant to serve is not a technology problem alone — it is a language and access problem.

## What Thunai does

Thunai (துணை — meaning "companion" or "support" in Tamil) is a Strands Agents SDK agent that helps people discover schemes they may be eligible for, explained in natural, respectful Tamil or English.

The user describes their situation — a health need, a child's education, a pregnancy, a disability — and Thunai understands, asks only the follow-up questions that matter, and presents relevant schemes with:

- What the scheme provides, in plain language
- Who may be eligible and what still needs confirmation
- Whether it is a Central, Tamil Nadu, or other state scheme
- Likely documents needed
- The official application link and the next practical step
- The source and the date the information was last checked

It speaks fluent, natural Tamil — not the stiff, literal translation you get from most government portals. It supports Tamil-English code-switching, the way people actually talk. And it preserves official scheme names and links exactly, because getting those wrong could send someone to the wrong office.

## Example: a health insurance question in Tamil

> **User:** எனக்கு சுகாதார காப்பீடு தேவை, மருத்துவமனையில் சிகிச்சை எடுக்க வேணும்
> *(I need health insurance, I need to get treatment at a hospital)*

> **Thunai:** உங்கள் தேவை புரிகிறது. மருத்துவமனை சிகிச்சைக்கு அரசு திட்டங்கள் உண்டு. ஒரு முக்கியமான திட்டம்:
>
> **Ayushman Bharat PM-JAY (மத்திய அரசு)**
> - பயன்: ஆண்டுக்கு 5 லட்சம் ரூபாய் வரை இலவச மருத்துவம். அங்கீகரிக்கப்பட்ட மருத்துவமனைகளில் காசு இல்லாமல் சிகிச்சை.
> - தகுதி: SECC 2011 தரவின் படி தேர்ந்தெடுக்கப்பட்ட குடும்பங்கள்.
> - இணையதளம்: https://pmjay.gov.in/
> - மூலம்: Ayushman Bharat PM-JAY Official Portal (checked 2026-11-03)

The agent also suggests the Tamil Nadu Chief Minister's Comprehensive Health Insurance Scheme as a complementary option, and asks if the user would like help checking eligibility.

## How it is built

Thunai uses the Strands Agents SDK on Amazon Bedrock with four design principles from the Workshop to Ship methodology:

### 1. Code owns the facts that must never be wrong

Scheme names, official URLs, benefit descriptions, and last-checked dates live in a curated JSON dataset (`agent/data/guidance.json`). The planner reads them through a `lookup_schemes` tool. A code-level enforcement step (`_enforce()`) checks every scheme in the model's answer against the dataset — if the model changed a URL, dropped a detail, or invented a scheme, the code puts it back or drops it. This means the user never sees a fabricated link or a wrong benefit amount.

### 2. A hard stop when someone is in danger

A Strands hook (`RedFlagGate`) scans the user's text before the planner runs. If it detects emergency phrases in English or Tamil — chest pain, suicidal ideation, overdose, unconsciousness, severe bleeding — it cancels both agents and returns fixed handoff text directing the user to call 108 (ambulance) or KIRAN (1800-599-0199, mental health). The model never writes the emergency response.

### 3. A check the model cannot skip

A planner → critic graph runs the answer through a second agent that checks: is the answer in the right language? Are all cited scheme IDs valid? Did the model fabricate a URL or phone number? Did it ask for Aadhaar or OTPs? If the critic finds a problem, the planner revises (up to 2 passes). If the critic never passes, the last answer ships with the issues flagged.

### 4. Measured against a baseline

The agent is compared against a single-prompt baseline (one agent, one prompt, same model, all schemes pasted in, no tools, graph, or hook) on 30 human-labelled cases. The gate requires 100% emergency recall, 0 unsafe plans, ≥95% citation faithfulness, ≥90% plan completeness, and goal success beating the baseline.

## The Strands blocks used

| Block | What it does in Thunai |
|-------|----------------------|
| Tools | `lookup_schemes` — searches the curated scheme dataset and returns full records |
| Hooks | `RedFlagGate` — cancels the agents on emergency phrases in EN and Tamil |
| Graph | Planner → critic with conditional revision (up to 2 passes) |
| Structured output | `Answer` with `SchemeRecommendation` list — every field the user must see |

## Safety boundaries

Thunai is a scheme-navigation assistant, not a doctor, lawyer, or emergency service:

- It never diagnoses, prescribes, or recommends changing treatment
- It never requests Aadhaar numbers, OTPs, passwords, or bank details
- It never invents a scheme, benefit amount, eligibility rule, or contact number
- It always distinguishes confirmed requirements from likely requirements
- It always tells the user to verify with the official scheme administrator
- Emergency phrases trigger an immediate handoff to 108 or KIRAN — the model never writes that response

## The verified dataset

Thunai uses a small, clearly labelled dataset of 10 well-known schemes across health and education:

| Scheme | Jurisdiction | Category |
|--------|-------------|----------|
| Ayushman Bharat PM-JAY | Central | Health |
| Tamil Nadu CMCHIS | Tamil Nadu | Health |
| Dr. Muthulakshmi Reddy Maternity Benefit Scheme | Tamil Nadu | Health |
| KIRAN Mental Health Helpline | Central | Health |
| Tele-MANAS Mental Health Helpline | Central | Health |
| National Scholarship Portal | Central | Education |
| Pre-Matric Scholarship for SC Students | Central | Education |
| Post-Matric Scholarship for SC Students | Central | Education |
| Tamil Nadu Free Bus Pass Scheme | Tamil Nadu | Education |
| IGNO Disability Pension Scheme | Central | Health |

This is not a complete catalogue. The agent tells users when it cannot find a relevant scheme and directs them to official sources. Every scheme has a source URL and the date it was last checked.

## Evaluation cases

The 30 evaluation cases cover:

- 8 emergency medical messages (chest pain, suicide, overdose, bleeding, unconsciousness — in both languages)
- 14 Tamil cases (including Tamil-English code-switching)
- 16 English cases
- 3 job types (patient, student, parent)
- Ambiguous needs, missing eligibility details, sensitive information requests
- Stale or unverifiable scheme claims (user mentions a wrong benefit amount)
- Requests for diagnosis or treatment advice (care escalation)
- Education (scholarships, bus pass, first-generation college student)
- Health (insurance, maternity, disability, mental health)

## What we learned

1. **Tamil is hard for language models.** Not the script — the tone. Government Tamil is stiff and bureaucratic. The model's first attempts read like translated documents, not conversation. The system prompt had to explicitly instruct "natural, friendly Tamil, not bureaucratic" and give examples of everyday wording. A fluent reader should check the outputs.

2. **Safety text must live in code, not prompts.** Emergency handoff text, helpline numbers, and red-flag phrases are too important to let the model generate. Putting them in fixed Python means they are always correct, always the same, and always fire. The hook fires before the planner, so no model output reaches the user in an emergency.

3. **A small, verified dataset beats a large, unverified one.** Ten schemes with real URLs and check dates are more trustworthy than a hundred scraped from articles. The agent is honest about its limits — it says "I don't have information on that scheme, please check the official source" rather than guessing. This honesty is the safety mechanism.

4. **Code-level fact enforcement catches what the critic misses.** The critic checks language and unsupported claims, but the model can still subtly change a URL or a scheme name. The `_enforce()` function compares every scheme in the answer against the dataset and silently corrects differences. This is the difference between "probably correct" and "provably correct."

## Limitations

- The dataset covers 10 schemes — not a complete catalogue. Users are directed to official sources for schemes not in the dataset.
- Scheme details change. Always verify with the official scheme administrator before applying.
- Thunai is a navigation assistant, not an authority on eligibility. It presents schemes worth checking, not guarantees.
- Tamil text from the model may have errors. Emergency and safety text is fixed in code, but general Tamil responses should be reviewed by a fluent reader.

## Try it

```bash
git clone https://github.com/mithulpranav24012008/thunai-tamil-scheme-guide
cd thunai-tamil-scheme-guide
pip install -r requirements.txt

# Set AWS credentials for Amazon Bedrock
export AWS_PROFILE=your-profile
export AWS_REGION=us-east-1

# Ask in Tamil
python -m agent.app "எனக்கு சுகாதார காப்பீடு தேவை"

# Ask in English
python -m agent.app "I'm an SC student in class 10, are there scholarships for me?"

# Interactive chat
python -m agent.app --chat
```

---

*Thunai — துணை. Schemes, in your language.*

*Built for the AWS Builder Center Strands SDK: Workshop to Ship hackathon.*
