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
