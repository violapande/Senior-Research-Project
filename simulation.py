import random
from openai import OpenAI
import string
import time
from pathlib import Path
from openai import OpenAI
import json  
from neo4j import GraphDatabase

client = OpenAI(api_key="placeholder")

class Agent:
    def __init__(self, name, memory=None):
        self.name = name
        self.confidence = 0.0
        self.culprit = "Unknown"
        self.memory = memory or []
        self.priority = 0.0

    def respond(self, context, last_speaker):
        prompt = f"""
You are {self.name} and possess ONLY the knowledge of a {self.name}. You do not possess knowledge 
outside your field of expertise, beyond preliminary basics.
What's been said so far is: "{context}"
Respond naturally and briefly to what {last_speaker} said, and share your 
current theory on the culprit given your thoughts and the context.
Your goal is to solve the case collaboratively with the other agents. Use your knowledge to your advantage.
Your memory: {self.memory}
In your response, include at the very end your current postulation for who/what the culprit may be (name/title only),
a confidence level (0.0 to 1.0) indicating how sure you are about this theory, and a priority score (0.0 to 1.0). 
Example format: Culprit_Name 0.75 0.90
If your suspect's name is multiple words, separate them with underscores. If others share your theory, use the same naming convention.
Your confidence level's deviation from 1.0 should reflect how much uncertainty you have based on the information available to you.
You should think critically, dissecting different aspects of the scenario to decrease this uncertainty. 
The priority score indicates your urgency to speak next in the conversation, heightened by:
    1) A new insight or piece of evidence you've uncovered
    2) A strong disagreement with another agent's theory
    3) A need to question another agent's statement
Do NOT include any other characters or punctuation around the culprit's name, confidence level, and priority score.
"""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        message = response.choices[0].message.content.strip()
        self.culprit = message.split()[-3]
        self.confidence = float(message.split()[-2].rstrip(string.punctuation))
        self.priority = float(message.split()[-1].rstrip(string.punctuation))
        self.memory.append(message)
        return message

def simulate_turns(agents, initial_context, msg=""):
    t = time.time()
    context = initial_context
    last_speaker = None
    while not all(a.confidence >= 0.9 for a in agents):
        possible_speakers = [a for a in agents if a.name != last_speaker]
        possible_speakers.sort(key=lambda x: x.priority, reverse=True)
        speaker = possible_speakers[0]
        message = speaker.respond(context, last_speaker or "You are the first speaker. Provide your initial thoughts.")
        context += f"\n{speaker.name}: {message}"
        print(f"{speaker.name}: {message}\n")
        msg += f"{speaker.name}: {message}\n"
        last_speaker = speaker.name
        if time.time() - t == 60 or all(a.culprit == agents[0].culprit and a.confidence >= 0.9 for a in agents):
            print(f"Consensus: {agents[0].culprit.replace('_', ' ')} with confidence {agents[0].confidence}")
            return context, msg
    return context, msg

# Example usage
agents = [Agent("Chemist"),
          Agent("Biologist"), 
          Agent("Historian"),
          Agent("Geologist"),
          ]

def temporal_graph():
    timeline_prompt = f"""
    From the crime case below, extract ALL events that involve:
    - actions
    - interactions
    - movements
    - discoveries
    - deaths
    - evidence handling

    For each event, return:
    - ID (E1, E2, etc.)
    - description
    - start_date (if known, else null)
    - start_time (24-hour decimal if known, else null)
    - end_time (if given / know duration, else null)
    - participants (list of names)
    - location (if known)

    Return ONLY valid JSON in this format:
    {{ "events": [{{
        "ID": "E1",
        "description": "...",
        "start_time": 21.75,
        "end_time": 22.0,
        "participants": ["Moss", "Vance"],
        "location": "Office"
        }}]
    }}

    DON'T include explanations, headers, or any unneeded text/formatting.

    CRIME CASE:
    {prompt}"""

    response = client.responses.create(model="gpt-4.1-mini", input=timeline_prompt)
    raw = response.output[0].content[0].text
    #print(raw)
    events = json.loads(raw)

    temporal_graph = {"events": {}, "relations": []}

    for event in events["events"]:
        temporal_graph["events"][event["ID"]] = event

    event_list = list(temporal_graph["events"].values())

    for i in range(len(event_list)):
        for j in range(len(event_list)):
            if i == j:
                continue
            e1 = event_list[i]
            e2 = event_list[j]
            if (e1["start_time"] and e2["start_time"]):
                if (e1["start_time"] < e2["start_time"]):
                    temporal_graph["relations"].append((e1["ID"], "before", e2["ID"]))
                elif (e1["start_time"] > e2["start_time"]):
                    temporal_graph["relations"].append((e2["ID"], "before", e1["ID"]))
                else:
                    temporal_graph["relations"].append((e1["ID"], "same time as", e2["ID"]))
    
    return temporal_graph

prompt = f"""CASE OVERVIEW
Date of Incident: March 15, 2024, approximately 10:30 PM
Location: Riverside University Observatory, Building 7, 3rd Floor
Victim: Dr. Helena Vance, 52, Professor of Astrophysics
Cause of Death: Acute cyanide poisoning
Circumstances: Found deceased in her locked office during a faculty evening event
SCENE DESCRIPTION
Dr. Vance was discovered slumped over her desk by a colleague who had a spare key. The door was locked from
the inside. A window was open approximately 6 inches. The room temperature was 58°F (external temperature:
52°F).
Items on Desk:
Empty ceramic coffee mug with residual dark liquid
Half-eaten almond biscotti on a napkin
Open laptop displaying astronomical data
Handwritten notes on university letterhead
Bottle of prescription digoxin (heart medication) - 30 tablets, prescribed 2 weeks prior
Reading glasses
Additional Room Contents:
Laboratory refrigerator (unplugged, door ajar, empty)
Bookshelf with astronomy texts and personal items
Photograph of Dr. Vance with three individuals (labeled on back: "Conference 2019 - Me, Richard, Patricia,
James")
Small potted bitter almonds plant on windowsill, recently watered
Waste bin containing: crumpled paper towels, empty yogurt container, torn envelope
AUTOPSY FINDINGS
Time of Death: Estimated 10:15-10:45 PM
Toxicology:
Blood cyanide level: 4.5 mg/L (lethal: >2 mg/L)
Digoxin level: 0.8 ng/mL (therapeutic range: 0.5-2.0 ng/mL)
Blood alcohol: 0.00%
Stomach contents: Partially digested cookie/biscuit material, coffee, trace amounts of apricot kernel
material
Physical Findings:
Cherry-red skin discoloration (characteristic of cyanide poisoning)
Bitter almond odor noted by medical examiner
No signs of struggle or defensive wounds
Petechial hemorrhaging in eyes (mild)
Genetic Screening:
CYP2D6 gene: Normal metabolizer status
Taste receptor TAS2R38: Homozygous recessive (cannot taste PTC/bitter compounds)
LABORATORY ANALYSIS
Coffee Mug Contents (Forensic Chemistry):
Liquid: Arabica coffee, traces of cyanide (0.3 mg/mL)
No fingerprints on exterior (wiped clean)
Lipstick mark on rim matches victim's shade
Ceramic glaze contains lead (vintage mug, pre-1980s manufacture)
Biscotti Analysis:
Commercially produced almond biscotti
Contains: wheat flour, sugar, almonds, eggs, vanilla
Amygdalin content: 42 mg per cookie (consistent with almond content)
No added toxins detected
Batch number traced to local Italian bakery, purchased 3 days prior
Bitter Almonds Plant (Botany):
Species: Prunus dulcis var. amara
Seeds contain 4-9% amygdalin by weight
Approximately 12 seeds missing from pods (empty pod casings in soil)
Plant care tag indicates purchased 6 months ago from "Garden Haven Nursery"
Soil moisture indicates watering within past 48 hours
Paper Analysis:
Handwritten notes contain astronomical calculations
Ink: Standard ballpoint, blue
Paper: University letterhead, watermarked 2023
Torn envelope in trash: Postmarked March 10, 2024, return address "Patricia Chen, 447 Oakwood Dr."
BIOCHEMISTRY DATA
Amygdalin Metabolism Pathway:
Amygdalin (found in bitter almonds, apricot kernels) is a cyanogenic glycoside
Requires enzymatic hydrolysis by β-glucosidase to release hydrogen cyanide
β-glucosidase is present in: intestinal bacteria, raw bitter almonds, apricot kernels
Human stomach acid (pH 1.5-3.5) alone cannot hydrolyze amygdalin significantly
Lethal dose of amygdalin: ~0.5-3.5 mg/kg body weight (if properly metabolized to cyanide)
Processing (roasting/baking above 160°C) destroys both amygdalin and β-glucosidase enzymes
Enzyme Activity Data:
β-glucosidase activity requires: pH 4.5-6.5 (optimal), temperature 35-45°C, substrate availability
Commercial baked goods (biscotti baked at 325°F/163°C for 25 minutes): β-glucosidase activity = 0%
(enzyme denatured)
Raw bitter almond seeds: β-glucosidase activity = 100%
WITNESS STATEMENTS
Dr. Richard Moss (Colleague, Physics Department):
"Helena and I had coffee in her office around 9:45 PM. I brought her a biscotti from the faculty lounge - there
was a whole tray from that Italian place. She made coffee in her office; she always kept grounds and a French
press there. I left around 10:00 PM. She seemed fine, just tired. The door locked behind me when I left."
Patricia Chen (Former Graduate Student):
"I sent Dr. Vance a letter last week returning a borrowed book. We had a falling out two years ago over
authorship credit on a paper. I've since moved on - I'm at a different university now. I hadn't spoken to her in
person since 2022."
James Okafor (Postdoctoral Researcher):
"I was in the building but on the first floor in the computer lab from 9:00 PM to 11:00 PM. Security footage
confirms this. I had no reason to see Dr. Vance that night."
Building Security:
"Dr. Moss's key card shows exit from Building 7 at 10:02 PM. No other faculty accessed the third floor between
10:00 PM and 10:45 PM when Dr. Vance was discovered. The victim's office window faces an alley with no
external cameras. Fire escape accessible from alley."
PHYSICAL EVIDENCE
Fingerprint Analysis:
Victim's prints: on laptop, prescription bottle, glasses, desk
Dr. Moss's prints: on door handle (interior), one chair
No unknown prints found
Coffee mug: wiped clean (no prints)
Timeline (Security Footage & Key Card Data):
9:30 PM: Dr. Vance enters Building 7
9:43 PM: Dr. Moss enters Building 7
10:02 PM: Dr. Moss exits Building 7
10:47 PM: Colleague discovers Dr. Vance (emergency call placed)
Digoxin Prescription Records:
Prescribed by Dr. Aaron Liu (cardiologist) on March 1, 2024
For atrial fibrillation management
Dosage: 0.25 mg daily
Pharmacy records: Filled March 1, 30-day supply
Pill count: 16 tablets present (14 days = 14 tablets consumed as expected)
BACKGROUND INFORMATION
Academic Context:
Dr. Vance was known for being meticulous about food safety after a colleague died from food poisoning in
2018. She avoided raw foods and always verified food sources. She grew the bitter almond plant as a "botanical
curiosity" and educational tool for discussing cyanogenic compounds in lectures.
Relationships:
Dr. Moss: 20-year colleague, friendly professional relationship
Patricia Chen: Former advisee, documented conflict over publication credit
James Okafor: Current postdoc, professional relationship, no known conflicts
Health History:
Atrial fibrillation (diagnosed 2023)
No history of depression or suicidal ideation
No known enemies aside from the academic dispute with Chen
Regular patient with no medication compliance issues
METEOROLOGICAL DATA
March 15, 2024, Evening Conditions:
Temperature: 52°F at 10:00 PM
Wind: 8 mph from northwest
Humidity: 73%
Barometric pressure: 30.12 inHg (rising)"""
# _, msg = simulate_turns(agents, prompt)


URI = "neo4j://127.0.0.1:7687"
AUTH = ("neo4j",
         "insert_your_own_pw_here")

driver = GraphDatabase.driver(URI, auth=AUTH)

def store_events(tx, event):
    tx.run("""
        MERGE (e:Event {ID: $ID})
        SET e.description = $desc,
            e.start_time = $start,
            e.end_time = $end,
            e.location = $loc""", 
         ID=event["ID"],
         desc=event["description"],
         start=event["start_time"],
         end=event["end_time"],
         loc=event["location"])
    
def link_participant(tx, eventID, person):
    tx.run("""
        MERGE (p:Person {name: $name})
        WITH p
        MATCH (e:Event {ID: $eID})
        MERGE (p)-[:INVOLVED_IN]->(e)
    """, name=person, eID=eventID)

def store_relation(tx, e1, relation, e2):
    rel_type = relation.replace(" ", "_").upper()
    query = f"""
        MATCH (a:Event {{ID: $ID1}})
        MATCH (b:Event {{ID: $ID2}})
        MERGE (a)-[:{rel_type}]->(b)"""
    tx.run(query, ID1=e1, ID2=e2)

def upload(graph):
    with driver.session(database="neo4j") as session:
        for event in graph["events"].values():
            print("Uploading event:", event["ID"])
            session.execute_write(store_events, event)

            for person in event["participants"]:
                session.execute_write(link_participant, event["ID"], person)

        for e1, rel, e2 in graph["relations"]:
            session.execute_write(store_relation, e1, rel, e2)


graph = temporal_graph()
("GRAPH CONTENTS:")
print(graph)
print("Event count:", len(graph["events"]))
print("Relation count:", len(graph["relations"]))
print()
#print(graph)
upload(graph)
