import random
import google.generativeai as genai
import string
import time
import pathlib
from pathlib import Path
import json
import os
from neo4j import GraphDatabase

genai.configure(api_key="placeholder")

class Agent:
    def __init__(self, name, memory=None):
        self.name = name
        self.confidence = 0.0
        self.culprit = "Unknown"
        self.memory = memory or []
        self.priority = 0.0

    def respond(self, context, last_speaker, temp, know):
        prompt = f"""
Share your current theory on the culprit given your thoughts and the context.
Use this temporal graph to inform your reasoning: {temp}
Use this knowledge graph to inform your reasoning: {know}
Your goal is to solve the case. Use your knowledge to your advantage.
Your memory: {self.memory}
In your response, include at the very end your current postulation for who/what the culprit may be (name/title only),
a confidence level (0.0 to 1.0) indicating how sure you are about this theory. 
Example format: Culprit_Name 0.75
If your suspect's name is multiple words, separate them with underscores.
Your confidence level's deviation from 1.0 should reflect how much uncertainty you have based on the information available to you.
You should think critically, dissecting different aspects of the scenario to decrease this uncertainty. 
Do NOT include any other characters or punctuation around the culprit's name or confidence level.
"""
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        message = response.text.strip()
        self.culprit = message.split()[-2]
        self.confidence = float(message.split()[-1].rstrip(string.punctuation))
        self.memory.append(message)
        return message

def simulate_turns(agents, initial_context, temp, know, msg=""):
    count = 0
    t = time.time()
    context = initial_context
    last_speaker = None
    while not all(a.confidence >= 0.9 for a in agents):
        possible_speakers = [a for a in agents if a.name != last_speaker]
        possible_speakers.sort(key=lambda x: x.priority, reverse=True)
        speaker = possible_speakers[0]
        message = speaker.respond(context, last_speaker or "You are the first speaker. Provide your initial thoughts.", temp, know)
        context += f"\n{speaker.name}: {message}"
        print(f"{speaker.name}: {message}\n")
        msg += f"{speaker.name}: {message}\n"
        last_speaker = speaker.name
        count += 1
        if count == 1 or time.time() - t == 60 or all(a.culprit == agents[0].culprit and a.confidence >= 0.9 for a in agents):
            print(f"Consensus: {agents[0].culprit.replace('_', ' ')} with confidence {agents[0].confidence}")
            return context, msg
    return context, msg

agents = [Agent("Agent")]

def temporal_graph():
    timeline_prompt = f"""
    From the crime case below, extract ALL events mentioned in the case file, including but not limited to:
    - alibis
    - actions
    - interactions
    - movements
    - discoveries
    - deaths
    - evidence handling

    For each event, return:
    - ID (E1, E2, etc.)
    - description
    - start_date (if known, else null; 
                  default Jan 1 if only year is given)
    - start_time (24-hour decimal if known, else null)
    - end_time (if given / know duration, else null)
    - participants (list of names)
    - location (if known)

    Return ONLY valid JSON in this format:
    {{ "events": [{{
        "ID": "E1",
        "description": "...",
        "start_date": (2024, 3, 15),
        "start_time": 21.75,
        "end_time": 22.0,
        "participants": ["Moss", "Vance"],
        "location": "Office"
        }}]
    }}

    DON'T include explanations, headers, or any unneeded text/formatting.

    CRIME CASE:
    {prompt}"""

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(timeline_prompt, generation_config={
        "response_mime_type": "application/json"
    })
    raw = response.text
    events = json.loads(raw)
    print(len(events))

    temporal_graph = {"events": {}, "relations": []}

    for event in events["events"]:
        temporal_graph["events"][event["ID"]] = event

    event_list = list(temporal_graph["events"].values())

    for i in range(len(event_list)):
        for j in range(i+1, len(event_list)):
            if i == j:
                continue
            e1 = event_list[i]
            e2 = event_list[j]
            if (e1["start_date"] and e2["start_date"]):
                if e1["start_date"] < e2["start_date"]:
                    temporal_graph["relations"].append((e1["ID"], "before", e2["ID"]))
                elif e1["start_date"] > e2["start_date"]:
                    temporal_graph["relations"].append((e2["ID"], "before", e1["ID"]))
                else:
                    if (e1["start_time"] is not None and e2["start_time"] is not None):
                        if (e1["start_time"] < e2["start_time"]):
                            temporal_graph["relations"].append((e1["ID"], "before", e2["ID"]))
                        elif (e1["start_time"] > e2["start_time"]):
                            temporal_graph["relations"].append((e2["ID"], "before", e1["ID"]))
                        else:
                            temporal_graph["relations"].append((e1["ID"], "same time as", e2["ID"]))
                    else:
                        temporal_graph["relations"].append((e1["ID"], "same time as", e2["ID"]))
    return temporal_graph

    NEO4J_URI,
    NEO4J_USER,
    NEO4J_PASSWORD

def knowledge_graph(case_text):
    
    ALLOWED_ENTITY_TYPES = [
        "Person",
        "Location",
        "Event",
        "Object",
        "Document",
        "MedicalFinding",
        "ChemicalFinding",
        "PhysicalEvidence",
        "TraceEvidence",
        "DigitalEvidence",
        "WitnessStatement",
        "Alibi",
        "Anomaly",
        "TimeStamp"
    ]

    ALLOWED_RELATIONSHIPS = [
        "WAS_AT",
        "PERFORMED",
        "INVOLVED_IN",
        "OCCURRED_AT",
        "FOUND_AT",
        "IMPLICATES",
        "DESCRIBES",
        "REFERS_TO",
        "CONNECTED_TO",
        "PRECEDES",
        "CONTRADICTS",
        "HAS_TIME"
    ]
    prompt = f"""
You are performing EXHAUSTIVE structured extraction for a crime investigation.

MANDATORY RULES:
1. Extract EVERY named person.
2. Extract ALL distinct factual elements as separate nodes.
3. Events MUST be extracted with associated TimeStamp nodes when time is stated or implied.
4. Prefer OVER-EXTRACTION to omission.
5. Use names EXACTLY as written.
6. Do NOT summarize.
7. Return ONLY valid JSON.

ALLOWED ENTITY TYPES:
{", ".join(ALLOWED_ENTITY_TYPES)}

ALLOWED RELATIONSHIPS:
{", ".join(ALLOWED_RELATIONSHIPS)}

Time handling rules:
- Every time or time range becomes a TimeStamp node.
- Events must connect to TimeStamp via HAS_TIME.
- If time is approximate, preserve wording exactly.

JSON FORMAT:
{{
  "entities": {{
    "Person": [{{"name": "..."}}],
    "Location": [{{"name": "..."}}],
    "Event": [{{"name": "..."}}],
    "Object": [{{"name": "..."}}],
    "Document": [{{"name": "..."}}],
    "MedicalFinding": [{{"name": "..."}}],
    "ChemicalFinding": [{{"name": "..."}}],
    "PhysicalEvidence": [{{"name": "..."}}],
    "TraceEvidence": [{{"name": "..."}}],
    "DigitalEvidence": [{{"name": "..."}}],
    "WitnessStatement": [{{"name": "..."}}],
    "Alibi": [{{"name": "..."}}],
    "Anomaly": [{{"name": "..."}}],
    "TimeStamp": [{{"name": "..."}}]
  }},
  "relationships": [
    {{"type": "...", "start": "...", "to": "..."}}
  ]
}}

TEXT:
{case_text}
"""

    model = genai.GenerativeModel("gemini-2.5-flash")

    response = model.generate_content(
    prompt,
    generation_config={
        "temperature": 0,
        "response_mime_type": "application/json"
    }
)
    output = response.text.strip()

    try:
        return json.loads(output)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON from LLM:\n" + output)

prompt = f"""📂 Case File: The Murders in the Rue
Morgue
This file compiles all available evidence and information regarding the brutal murders of
Madame L'Espanaye and her daughter in Paris in the summer of 1840.
1. Case Summary 📝
On the morning of July 7, 1840, in an old house on the Rue Morgue, an old woman, Mrs.
L'Espanaye, and her unmarried daughter were found brutally murdered on the fourth floor. The
room was locked from the inside, and all windows were secured. The police found no forced
entry or means of escape, leading to extreme confusion. The mother's body was later
discovered outside the house, behind the building.
2. Victims and Residence Details 🏠
Victims
●
Mrs. L'Espanaye (Old Woman): Owner of the house. Had withdrawn a large amount
of gold from her bank three days before the murder.
●
Daughter (Unmarried): Lived with her mother.
Residence
●
Location: Old house on the Rue Morgue, Paris.
●
Occupants: The women lived alone on the fourth floor.
●
Observations: Few people were ever seen entering or going in or out of the house.
3. Crime Scene - Fourth Floor Room 🩸
Entry and Exit Analysis (The Locked Room Mystery)
●
Door: Found firmly closed, locked with the key inside. Neighbors had to force it open.
●
Windows: Two windows were closed and firmly locked on the inside.
○
Finding by Police: Both windows appeared to be secured by strong iron nails.
○
Finding by Dupin: The strong iron nail holding the second window closed was
broken. The top part (the head) was detachable. This allowed the window to be
opened and then closed, making the nail look whole and tightly secured from the
inside. Dupin also discovered a hidden, inner lock button that secured the
window.
●
Other Openings: The openings over the fireplace were too small for anyone to have
escaped.
Condition and Objects Found
●
Condition: The room was in "the wildest possible order.
" Broken chairs and tables
were lying all around. Everything had been taken off the single bed and thrown into the
middle of the floor.
●
Blood: Blood was everywhere: on the floor, bed, and walls.
●
Objects Found:
○
A sharp knife covered with blood.
○
Long gray hair, bloody, seeming to have been pulled from a human head (later
analyzed as not human hair).
○
Two bags containing a large amount of money in gold were found.
○
Four pieces of gold, an earring, and several silver objects were also found.
○
An open box with a few old letters and papers was found under the bed covers.
○
Clothes were thrown around, but nothing appeared to have been stolen (motive
not theft).
4. Details of the Bodies 💀
The Daughter
●
Location Found: Found in the opening over the fireplace, put up head-down. The body
was still warm.
●
Injuries: Died from dark, deep marks on her neck made by strong fingers, indicating
strangulation. Dupin's analysis proved the marks were too large for a human hand.
Mrs. L'Espanaye (Mother)
●
Location Found: Found outside, behind the building.
●
Injuries: Her neck was almost cut through; her head fell off when they tried to lift her.
The injuries were described as "badly marked and broken" and could only have come
from a very powerful man.
5. Neighbor Testimony (Voices Heard) 🗣️
A group of neighbors rushing up the stairs heard two voices from the room before entering.
●
Low/Soft Voice: All witnesses agreed this was a Frenchman's voice. Heard it say "My
God!" in French.
●
High/Strange Voice: All witnesses agreed this voice was not French and sounded like
a foreigner, but each witness named a different nationality (Spanish, English, Italian).
No witness could understand any separate word from this voice.
6. Physical Evidence Analysis by Dupin 🔎
●
Escape Route: Dupin determined the murderer escaped through the second window.
●
Access Point: To reach the fourth-floor window, the perpetrator used a long, thin metal
pole (lightning rod) running from the top of the building to the ground. Climbing this
pole would require "very special strength and special training.
"
●
Finger Marks: A test with a wooden block the size of the daughter's neck proved that
the finger marks were too large to have been made by a human hand.
●
Hair: The hair found was analyzed and determined to be not human hair.
●
Motive: Could not have been money, as almost all the gold was left in the room.
"""

temp = temporal_graph()
# know = knowledge_graph(prompt)
_, msg = simulate_turns(agents, prompt, temp, None)
# #print(temp)

# URI = "neo4j://127.0.0.1:7687"
# AUTH = ("neo4j",
#          "placeholder_password")

# driver = GraphDatabase.driver(URI, auth=AUTH)

# def store_events(tx, event):
#     tx.run("""
#         MERGE (e:Event {ID: $ID})
#         SET e.description = $desc,
#             e.start_time = $start,
#             e.end_time = $end,
#             e.location = $loc""", 
#          ID=event["ID"],
#          desc=event["description"],
#          start=event["start_time"],
#          end=event["end_time"],
#          loc=event["location"])
    
# def link_participant(tx, eventID, person):
#     tx.run("""
#         MERGE (p:Person {name: $name})
#         WITH p
#         MATCH (e:Event {ID: $eID})
#         MERGE (p)-[:INVOLVED_IN]->(e)
#     """, name=person, eID=eventID)

# def store_relation(tx, e1, relation, e2):
#     rel_type = relation.replace(" ", "_").upper()
#     query = f"""
#         MATCH (a:Event {{ID: $ID1}})
#         MATCH (b:Event {{ID: $ID2}})
#         MERGE (a)-[:{rel_type}]->(b)"""
#     tx.run(query, ID1=e1, ID2=e2)

# def upload(graph):
#     with driver.session(database="neo4j") as session:
#         session.run("MATCH (n) DETACH DELETE n")
#         for event in graph["events"].values():
#             print("Uploading event:", event["ID"])
#             session.execute_write(store_events, event)

#             for person in event["participants"]:
#                 session.execute_write(link_participant, event["ID"], person)

#         for e1, rel, e2 in graph["relations"]:
#             session.execute_write(store_relation, e1, rel, e2)

# graph = temporal_graph()
# ("GRAPH CONTENTS:")
# print(graph)
# print("Event count:", len(graph["events"]))
# print("Relation count:", len(graph["relations"]))
# print()
# print(graph)
# upload(graph)
