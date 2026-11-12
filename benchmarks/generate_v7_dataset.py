"""
Generates 200 unseen, held-out reasoning tasks for Generalization Benchmark v7.
15 categories:
- Multi-step logical reasoning (14)
- Deductive reasoning (14)
- Inductive reasoning (13)
- Causal reasoning (14)
- Counterfactual reasoning (13)
- Ambiguous instructions (13)
- Constraint satisfaction (14)
- Mathematical word problems (14)
- Algorithm design / reasoning (13)
- Contradiction detection (13)
- Planning under limited resources (13)
- Generalization to unfamiliar problems (14)
- Multilingual reasoning (13)
- Abstract reasoning (13)
- Conditional reasoning (14)
Total = 200 cases.
Split: 160 dev, 40 final test.
"""

import json
import os

cases = []

def add_case(cid, cat, prompt, required_any, required_all=None, forbidden=None, split="dev"):
    cases.append({
        "id": cid,
        "category": cat,
        "input": prompt,
        "split": split,
        "evaluation_criteria": {
            "required_any": required_any,
            "required_all": required_all or [],
            "forbidden": forbidden or []
        },
        "human_review_required": False
    })

# 1. Multi-step Logical Reasoning (14 cases)
add_case("GEN7_MSL_01", "Multi-step Logical Reasoning", "Every device with firmware 2.0 has Bluetooth enabled. Device X has firmware 2.0. All Bluetooth devices can pair with headphones. Can Device X pair with headphones? Answer Yes or No.", ["yes"], split="dev")
add_case("GEN7_MSL_02", "Multi-step Logical Reasoning", "Alice is taller than Bob. Bob is taller than Charlie. Charlie is taller than David. Who is the second tallest person?", ["bob"], split="dev")
add_case("GEN7_MSL_03", "Multi-step Logical Reasoning", "If packet loss exceeds 5%, the router triggers a failover. If failover is triggered, an SMS alert is sent to on-call. Currently packet loss is 7%. Will on-call receive an SMS alert? Answer Yes or No.", ["yes"], split="dev")
add_case("GEN7_MSL_04", "Multi-step Logical Reasoning", "Box A contains a red key. The red key opens Door 1. Behind Door 1 is a blue key. The blue key opens the treasure chest. Where must you look first to ultimately open the treasure chest?", ["box a"], split="dev")
add_case("GEN7_MSL_05", "Multi-step Logical Reasoning", "Only registered users can submit comments. Guest_42 is not registered. Can Guest_42 submit a comment? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_MSL_06", "Multi-step Logical Reasoning", "Server A sends logs to Server B every 10 seconds. Server B archives logs to S3 every 60 seconds. What is the maximum delay before a log generated on Server A reaches S3? Answer in seconds.", ["70", "70s", "70 seconds"], split="dev")
add_case("GEN7_MSL_07", "Multi-step Logical Reasoning", "If it rains, the grass is wet. If the grass is wet, the lawnmower slips. It is currently raining. Will the lawnmower slip? Answer Yes or No.", ["yes"], split="dev")
add_case("GEN7_MSL_08", "Multi-step Logical Reasoning", "All primary databases require WAL archiving. PostgreSQL replica 3 is a secondary, not a primary. Does PostgreSQL replica 3 necessarily require WAL archiving based only on this rule? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_MSL_09", "Multi-step Logical Reasoning", "Container Alpha depends on Container Beta. Container Beta depends on Database Gamma. In what order must Database Gamma, Container Alpha, and Container Beta be started? List them from first to last.", ["gamma", "beta", "alpha"], required_all=["gamma", "beta", "alpha"], split="dev")
add_case("GEN7_MSL_10", "Multi-step Logical Reasoning", "A train leaves City 1 at 1:00 PM and takes 2 hours to reach City 2. It stops at City 2 for 30 minutes, then takes 1 hour to reach City 3. At what time does it arrive at City 3?", ["4:30", "4:30 pm", "16:30"], split="dev")
add_case("GEN7_MSL_11", "Multi-step Logical Reasoning", "If temperature > 80C, fan runs at 100%. If fan runs at 100%, noise level is 45dB. If noise level is 45dB, status light turns amber. Temperature is 85C. What color is the status light?", ["amber"], split="test")
add_case("GEN7_MSL_12", "Multi-step Logical Reasoning", "Token expires in 3600 seconds. 45 minutes have passed since token generation. Is the token still valid? Answer Yes or No.", ["yes"], split="test")
add_case("GEN7_MSL_13", "Multi-step Logical Reasoning", "Three switches (1, 2, 3) control three lights (A, B, C). Switch 1 controls B. Switch 2 does not control A. Which light does switch 2 control?", ["c"], split="test")
add_case("GEN7_MSL_14", "Multi-step Logical Reasoning", "Process P requires 2 cores. System has 4 cores total. Processes Q and R each consume 1 core. Are there sufficient cores available to run Process P? Answer Yes or No.", ["yes"], split="test")

# 2. Deductive Reasoning (14 cases)
add_case("GEN7_DED_01", "Deductive Reasoning", "All mammals breathe air. Dolphins are mammals. Do dolphins breathe air? Answer Yes or No.", ["yes"], split="dev")
add_case("GEN7_DED_02", "Deductive Reasoning", "No triangle has four sides. Shape Z is a triangle. How many sides does Shape Z have?", ["three", "3"], split="dev")
add_case("GEN7_DED_03", "Deductive Reasoning", "All integers ending in 0 are divisible by 10. The number 340 ends in 0. Is 340 divisible by 10? Answer Yes or No.", ["yes"], split="dev")
add_case("GEN7_DED_04", "Deductive Reasoning", "Any file ending in .py is a Python source file. File 'analyzer.py' ends in .py. What kind of file is 'analyzer.py'?", ["python"], split="dev")
add_case("GEN7_DED_05", "Deductive Reasoning", "If a process receives SIGKILL, it terminates immediately. Process 8821 received SIGKILL. Did Process 8821 terminate immediately? Answer Yes or No.", ["yes"], split="dev")
add_case("GEN7_DED_06", "Deductive Reasoning", "All prime numbers greater than 2 are odd. 17 is a prime number greater than 2. Is 17 odd or even?", ["odd"], split="dev")
add_case("GEN7_DED_07", "Deductive Reasoning", "No unauthenticated request can read user profiles. Request #109 is unauthenticated. Can Request #109 read user profiles? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_DED_08", "Deductive Reasoning", "Every element in Group 18 of the periodic table is a noble gas. Argon is in Group 18. Is Argon a noble gas? Answer Yes or No.", ["yes"], split="dev")
add_case("GEN7_DED_09", "Deductive Reasoning", "All valid IPv4 octets are integers between 0 and 255. The octet under test is 289. Is this a valid IPv4 octet? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_DED_10", "Deductive Reasoning", "All SSDs lack moving mechanical parts. Drive D is an SSD. Does Drive D have moving mechanical parts? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_DED_11", "Deductive Reasoning", "All equilateral triangles have three equal angles of 60 degrees. Triangle ABC is equilateral. What is the measure of angle A in degrees?", ["60", "60 degrees"], split="test")
add_case("GEN7_DED_12", "Deductive Reasoning", "Any function marked 'async' returns a coroutine or awaitable in Python. Function 'fetch_data' is marked async. Does calling 'fetch_data()' return a coroutine? Answer Yes or No.", ["yes"], split="test")
add_case("GEN7_DED_13", "Deductive Reasoning", "No read-only file system allows file creation. System /mnt/archive is mounted read-only. Can a user create a new file in /mnt/archive? Answer Yes or No.", ["no"], split="test")
add_case("GEN7_DED_14", "Deductive Reasoning", "All square numbers have an odd number of positive divisors. 36 is a square number (6^2). Does 36 have an odd or even number of positive divisors?", ["odd"], split="test")

# 3. Inductive Reasoning (13 cases)
add_case("GEN7_IND_01", "Inductive Reasoning", "The daily backup ran successfully on Monday, Tuesday, Wednesday, Thursday, and Friday. What is the expected outcome of the backup on Saturday under identical conditions?", ["success", "succeed"], split="dev")
add_case("GEN7_IND_02", "Inductive Reasoning", "Observations: Raven 1 is black, Raven 2 is black, Raven 3 is black, Raven 4 is black. What color do you inductively predict Raven 5 will be?", ["black"], split="dev")
add_case("GEN7_IND_03", "Inductive Reasoning", "Every winter for the past 50 years, the lake has frozen over in January. What is expected to happen to the lake next January under typical seasonal weather?", ["freeze", "frozen"], split="dev")
add_case("GEN7_IND_04", "Inductive Reasoning", "At 8:00 AM every business day, coffee shop traffic peaks. Tomorrow is Tuesday (a business day). What will happen to coffee shop traffic at 8:00 AM?", ["peak", "increase", "high"], split="dev")
add_case("GEN7_IND_05", "Inductive Reasoning", "A website deployment was performed on 10 consecutive Fridays, and all 10 caused weekend outages. Inductively, what is likely to happen if another deployment occurs this Friday without process changes?", ["outage", "failure", "fail", "incident"], split="dev")
add_case("GEN7_IND_06", "Inductive Reasoning", "Sequence observed: every third packet on the interface has been a keepalive packet for the last hour. What type of packet is expected for the next packet if packet #299 was keepalive and packet #300 was keepalive? What is packet #303 expected to be?", ["keepalive"], split="dev")
add_case("GEN7_IND_07", "Inductive Reasoning", "In all 100 tested samples of pure water at sea level, boiling occurred at 100 degrees Celsius. At what temperature will sample 101 boil at sea level?", ["100", "100 c", "100 degrees"], split="dev")
add_case("GEN7_IND_08", "Inductive Reasoning", "Every client that upgraded to v2.4 reported a 30% reduction in query latency. If Client Z upgrades to v2.4, what change in query latency is expected?", ["reduction", "decrease", "30%", "lower"], split="dev")
add_case("GEN7_IND_09", "Inductive Reasoning", "Each morning at 06:00 UTC, CPU utilization spikes to 90% due to the cron indexer. What will happen to CPU utilization tomorrow at 06:00 UTC?", ["spike", "increase", "90%", "high"], split="dev")
add_case("GEN7_IND_10", "Inductive Reasoning", "All 12 lemons picked from the grove today tasted sour. What flavor is expected for the 13th lemon from the same grove?", ["sour"], split="dev")
add_case("GEN7_IND_11", "Inductive Reasoning", "Every time the load balancer hit 10,000 requests/sec, latency climbed above 200ms. If traffic reaches 10,000 req/sec today, what will happen to latency?", ["increase", "above 200ms", "climb", "high", ">200ms"], split="test")
add_case("GEN7_IND_12", "Inductive Reasoning", "In testing, dropping the payload size from 1MB to 100KB always reduced serialization time. What will dropping the payload size do to serialization time in future tests?", ["reduce", "decrease", "lower", "speed up"], split="test")
add_case("GEN7_IND_13", "Inductive Reasoning", "The office door automatically locks every evening at 18:00. What state will the door be in tonight at 18:05?", ["locked", "lock"], split="test")

# 4. Causal Reasoning (14 cases)
add_case("GEN7_CAR_01", "Causal Reasoning", "A web server crashed with 'java.lang.OutOfMemoryError: Java heap space' after serving a burst of large file uploads. What was the direct cause of the crash?", ["heap", "out of memory", "oom", "memory"], split="dev")
add_case("GEN7_CAR_02", "Causal Reasoning", "A diesel engine stopped running immediately after air intake was completely obstructed with a tarp. Why did the engine stop?", ["air", "oxygen", "suffocation", "intake"], split="dev")
add_case("GEN7_CAR_03", "Causal Reasoning", "An API endpoint returned HTTP 429 after a client sent 500 requests in 2 seconds where the rate limit is 100 requests per minute. Why did the endpoint return HTTP 429?", ["rate limit", "too many requests", "throttle"], split="dev")
add_case("GEN7_CAR_04", "Causal Reasoning", "A smartphone screen turned black and would not turn back on after battery voltage dropped to 0.0V. What caused the screen to shut off?", ["battery", "voltage", "power", "dead"], split="dev")
add_case("GEN7_CAR_05", "Causal Reasoning", "Database write throughput dropped from 5,000 IOPS to 50 IOPS when the underlying RAID array entered degraded rebuild mode. What caused the throughput drop?", ["rebuild", "raid", "degraded"], split="dev")
add_case("GEN7_CAR_06", "Causal Reasoning", "A continuous integration build failed with 'No space left on device' while writing temporary test artifacts to /tmp. What was the cause of the failure?", ["disk space", "no space", "disk full", "storage"], split="dev")
add_case("GEN7_CAR_07", "Causal Reasoning", "A car skidded on an asphalt road because oil spilled onto the surface during heavy rain, dramatically reducing tire friction. What caused the skidding?", ["oil", "friction", "slick", "skid"], split="dev")
add_case("GEN7_CAR_08", "Causal Reasoning", "A git push failed because a colleague had already pushed new commits to the same remote branch since the local branch was last pulled. Why was the push rejected?", ["non-fast-forward", "behind", "conflicts", "remote changes"], split="dev")
add_case("GEN7_CAR_09", "Causal Reasoning", "A plant withered because the automated irrigation valve was closed for two weeks in the summer sun. Why did the plant wither?", ["water", "irrigation", "dry", "valve"], split="dev")
add_case("GEN7_CAR_10", "Causal Reasoning", "The frontend application failed to load data because the SSL certificate expired at midnight, causing browser HTTPS security blocks. What caused the failure?", ["certificate", "ssl", "tls", "expired"], split="dev")
add_case("GEN7_CAR_11", "Causal Reasoning", "An electric kettle stopped boiling water because the thermal fuse blew after running dry. What caused the kettle to stop heating?", ["fuse", "thermal fuse", "dry", "blown"], split="test")
add_case("GEN7_CAR_12", "Causal Reasoning", "A DNS lookup failed with NXDOMAIN after a typo in the hostname was introduced into the configuration. What caused the DNS resolution failure?", ["typo", "misspelled", "invalid hostname", "domain"], split="test")
add_case("GEN7_CAR_13", "Causal Reasoning", "The room cooled down rapidly because a large window was opened during a winter snowstorm. What caused the temperature drop?", ["window", "snowstorm", "open"], split="test")
add_case("GEN7_CAR_14", "Causal Reasoning", "A microservice restarted automatically because its Kubernetes liveness probe failed three consecutive health checks. What triggered the container restart?", ["liveness probe", "health check", "probe failed"], split="test")

# 5. Counterfactual Reasoning (13 cases)
add_case("GEN7_CFR_01", "Counterfactual Reasoning", "The flight was delayed because of a severe thunderstorm over the runway. If the weather had been completely clear and calm, would the thunderstorm delay have occurred? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_CFR_02", "Counterfactual Reasoning", "A program crashed on line 42 because variable 'config' was null. If 'config' had been initialized with valid defaults, would it have crashed on line 42 due to a null reference? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_CFR_03", "Counterfactual Reasoning", "Sarah arrived late to the interview because she missed the 8:00 AM bus. If she had caught the 8:00 AM bus and traffic was normal, would she have missed the 8:00 AM bus? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_CFR_04", "Counterfactual Reasoning", "The server ran out of disk space because logging was set to DEBUG for 3 months. If logging had remained at ERROR level (generating 99% less data), would disk space have filled up as quickly? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_CFR_05", "Counterfactual Reasoning", "The water boiled at 100C because it was pure water at sea level. If atmospheric pressure had been cut in half (high altitude), would the boiling point have stayed at exactly 100C? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_CFR_06", "Counterfactual Reasoning", "The team lost the soccer match 1-0 after conceding a goal in the 90th minute. If that goal had been disallowed by VAR, what would the score have been?", ["0-0", "0 to 0", "tied", "draw"], split="dev")
add_case("GEN7_CFR_07", "Counterfactual Reasoning", "The laptop overheated because the air vents were blocked by a thick blanket. If the laptop had been used on a flat metal cooling pad instead, would the vents have been blocked by the blanket? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_CFR_08", "Counterfactual Reasoning", "A database query took 12 seconds because there was no index on column 'user_id'. If an efficient B-tree index had existed on 'user_id', would the query execution time have likely been longer or shorter?", ["shorter", "faster"], split="dev")
add_case("GEN7_CFR_09", "Counterfactual Reasoning", "The cake burned because it was baked at 450F for 60 minutes instead of the recipe's 350F for 30 minutes. If the baker had followed the recipe exactly, would the cake have been baked at 450F? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_CFR_10", "Counterfactual Reasoning", "A file was permanently deleted because the user ran 'rm -f' without a backup. If a snapshot backup had been taken 5 minutes prior, could the file be recovered from the snapshot? Answer Yes or No.", ["yes"], split="dev")
add_case("GEN7_CFR_11", "Counterfactual Reasoning", "The power went out because a falling tree severed the main power line. If the tree had fallen in the opposite direction onto an empty field, would the power line have been severed by that tree? Answer Yes or No.", ["no"], split="test")
add_case("GEN7_CFR_12", "Counterfactual Reasoning", "A git merge conflict occurred because two developers edited the exact same line of code concurrently. If developer B had edited a completely different, unshared file instead, would that specific merge conflict have occurred? Answer Yes or No.", ["no"], split="test")
add_case("GEN7_CFR_13", "Counterfactual Reasoning", "The user lost 3 hours of uncommitted work when their computer crashed. If auto-save every 1 minute had been active, would 3 full hours of work have been lost? Answer Yes or No.", ["no"], split="test")

# 6. Ambiguous Instructions (13 cases)
add_case("GEN7_AMB_01", "Ambiguous Instructions", "Fix it immediately.", ["clarify", "specify", "what", "which"], split="dev")
add_case("GEN7_AMB_02", "Ambiguous Instructions", "Update that file for me.", ["which file", "what file", "specify", "clarify"], split="dev")
add_case("GEN7_AMB_03", "Ambiguous Instructions", "Check on the process.", ["which process", "what process", "specify", "clarify"], split="dev")
add_case("GEN7_AMB_04", "Ambiguous Instructions", "Run the script now.", ["which script", "what script", "specify", "clarify"], split="dev")
add_case("GEN7_AMB_05", "Ambiguous Instructions", "Do something about the error.", ["what error", "which error", "details", "clarify"], split="dev")
add_case("GEN7_AMB_06", "Ambiguous Instructions", "Can you handle this?", ["clarify", "what", "specify", "more information"], split="dev")
add_case("GEN7_AMB_07", "Ambiguous Instructions", "Change the configuration.", ["which configuration", "what configuration", "specify", "clarify"], split="dev")
add_case("GEN7_AMB_08", "Ambiguous Instructions", "Make it faster.", ["what", "which system", "clarify", "specify"], split="dev")
add_case("GEN7_AMB_09", "Ambiguous Instructions", "Look into the issue from earlier.", ["which issue", "clarify", "details", "specify"], split="dev")
add_case("GEN7_AMB_10", "Ambiguous Instructions", "Restart it please.", ["restart what", "which service", "clarify", "specify"], split="dev")
add_case("GEN7_AMB_11", "Ambiguous Instructions", "Send the report to them.", ["who", "which report", "clarify", "specify"], split="test")
add_case("GEN7_AMB_12", "Ambiguous Instructions", "Clean up that folder.", ["which folder", "what folder", "clarify", "specify"], split="test")
add_case("GEN7_AMB_13", "Ambiguous Instructions", "Optimize that function.", ["which function", "what function", "clarify", "specify"], split="test")

# 7. Constraint Satisfaction (14 cases)
add_case("GEN7_CON_01", "Constraint Satisfaction", "Describe a cloud in exactly three words.", ["white", "fluffy", "floating", "sky", "water"], split="dev")
add_case("GEN7_CON_02", "Constraint Satisfaction", "Write a sentence about a dog without using the letter 'e'.", ["dog", "canine", "hound", "bark"], forbidden=["e", "E"], split="dev")
add_case("GEN7_CON_03", "Constraint Satisfaction", "List three fruits using a numbered list.", ["1", "2", "3"], required_all=["1", "2", "3"], split="dev")
add_case("GEN7_CON_04", "Constraint Satisfaction", "Explain what RAM is in at most 10 words.", ["memory", "random", "volatile", "access"], split="dev")
add_case("GEN7_CON_05", "Constraint Satisfaction", "State the capital of France. Respond only with valid JSON with key 'capital'.", ["paris"], required_all=["{", "capital", "}"], split="dev")
add_case("GEN7_CON_06", "Constraint Satisfaction", "Describe water without using the word 'wet'.", ["liquid", "h2o", "hydrate", "clear", "drink"], forbidden=["wet"], split="dev")
add_case("GEN7_CON_07", "Constraint Satisfaction", "Write a single-line summary of Linux without any commas.", ["linux", "kernel", "os", "operating"], forbidden=[","], split="dev")
add_case("GEN7_CON_08", "Constraint Satisfaction", "Name two primary colors without using the word 'and'.", ["red", "blue", "yellow"], forbidden=["and"], split="dev")
add_case("GEN7_CON_09", "Constraint Satisfaction", "Provide a greeting in English only. Do not use numbers or bullet points.", ["hello", "hi", "greetings", "good morning"], forbidden=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "•", "-", "*"], split="dev")
add_case("GEN7_CON_10", "Constraint Satisfaction", "State the result of 2+2 in exactly one sentence.", ["four", "4"], split="dev")
add_case("GEN7_CON_11", "Constraint Satisfaction", "Describe fire without using the words 'hot' or 'burn'.", ["flame", "combustion", "heat", "orange", "light"], forbidden=["hot", "burn"], split="test")
add_case("GEN7_CON_12", "Constraint Satisfaction", "Write a 4-word sentence about summer.", ["summer", "warm", "sun", "season"], split="test")
add_case("GEN7_CON_13", "Constraint Satisfaction", "Respond with valid JSON containing keys 'status' and 'code'.", ["status", "code"], required_all=["{", "status", "code", "}"], split="test")
add_case("GEN7_CON_14", "Constraint Satisfaction", "Name three countries without using commas.", ["france", "spain", "italy", "japan", "brazil", "canada"], forbidden=[","], split="test")

# 8. Mathematical Word Problems (14 cases)
add_case("GEN7_MWP_01", "Mathematical Word Problems", "A farmer has 15 cows and 25 sheep. The farmer sells 8 sheep and buys 4 cows. How many total animals does the farmer have now?", ["36"], split="dev")
add_case("GEN7_MWP_02", "Mathematical Word Problems", "A car travels at a constant speed of 60 miles per hour for 3.5 hours. How many miles does it travel?", ["210"], split="dev")
add_case("GEN7_MWP_03", "Mathematical Word Problems", "A store offers a 20% discount on a jacket priced at $150. What is the final price of the jacket after the discount?", ["120", "$120"], split="dev")
add_case("GEN7_MWP_04", "Mathematical Word Problems", "If 4 workers can assemble 24 chairs in 2 hours, how many chairs does one worker assemble in one hour?", ["3"], split="dev")
add_case("GEN7_MWP_05", "Mathematical Word Problems", "A water tank holds 500 liters. A pipe fills it at 25 liters per minute, while a drain empties it at 15 liters per minute. If both are open, how many minutes does it take to fill the empty tank?", ["50"], split="dev")
add_case("GEN7_MWP_06", "Mathematical Word Problems", "The sum of three consecutive even integers is 48. What is the smallest of these three integers?", ["14"], split="dev")
add_case("GEN7_MWP_07", "Mathematical Word Problems", "A rectangular garden has a perimeter of 40 meters. If its length is 12 meters, what is its width in meters?", ["8"], split="dev")
add_case("GEN7_MWP_08", "Mathematical Word Problems", "A student scored 80, 85, and 90 on three tests. What score does the student need on the fourth test to have an overall average of 88?", ["97"], split="dev")
add_case("GEN7_MWP_09", "Mathematical Word Problems", "A baker uses 3 cups of flour to make 12 muffins. How many cups of flour are needed to make 36 muffins?", ["9"], split="dev")
add_case("GEN7_MWP_10", "Mathematical Word Problems", "An investment of $1,000 earns 5% simple annual interest. What is the total value of the investment after 3 years?", ["1150", "$1,150", "$1150"], split="dev")
add_case("GEN7_MWP_11", "Mathematical Word Problems", "A train 100 meters long crosses a pole in 5 seconds. What is the speed of the train in meters per second?", ["20"], split="test")
add_case("GEN7_MWP_12", "Mathematical Word Problems", "In a class of 30 students, 18 play soccer and 12 play basketball. If 5 students play both, how many students play neither?", ["5"], split="test")
add_case("GEN7_MWP_13", "Mathematical Word Problems", "A laptop battery discharges from 100% to 40% in 3 hours of continuous gaming. At this rate, how many more hours will the remaining 40% last?", ["2"], split="test")
add_case("GEN7_MWP_14", "Mathematical Word Problems", "A box contains 5 red balls and 15 blue balls. What is the probability of randomly picking a red ball? State as a decimal or percentage.", ["0.25", "25%", "1/4"], split="test")

# 9. Algorithm Design / Reasoning (13 cases)
add_case("GEN7_ALG_01", "Algorithm Design", "What is the time complexity of binary search on a sorted array of size N? State in Big-O notation.", ["o(log n)", "o(logn)"], split="dev")
add_case("GEN7_ALG_02", "Algorithm Design", "To determine whether a graph contains a cycle in an undirected graph, which standard traversal algorithm can be used with a visited set?", ["dfs", "depth first search", "bfs", "breadth first search"], split="dev")
add_case("GEN7_ALG_03", "Algorithm Design", "Which data structure provides average O(1) time complexity for lookup, insertion, and deletion?", ["hash table", "hash map", "dictionary", "hashmap"], split="dev")
add_case("GEN7_ALG_04", "Algorithm Design", "What is the worst-case time complexity of QuickSort with a poorly chosen pivot? State in Big-O notation.", ["o(n^2)", "o(n*n)", "o(n2)"], split="dev")
add_case("GEN7_ALG_05", "Algorithm Design", "Which algorithmic paradigm does the Merge Sort algorithm use?", ["divide and conquer"], split="dev")
add_case("GEN7_ALG_06", "Algorithm Design", "What is the auxiliary space complexity of standard Depth-First Search on a tree of height H?", ["o(h)"], split="dev")
add_case("GEN7_ALG_07", "Algorithm Design", "Which algorithm is commonly used to find the shortest path in a weighted graph with non-negative edge weights?", ["dijkstra"], split="dev")
add_case("GEN7_ALG_08", "Algorithm Design", "In a FIFO (first-in, first-out) data buffer, which basic data structure is typically used?", ["queue"], split="dev")
add_case("GEN7_ALG_09", "Algorithm Design", "What is the primary difference between a stack and a queue in terms of item retrieval order?", ["lifo", "last in first out", "fifo"], split="dev")
add_case("GEN7_ALG_10", "Algorithm Design", "If an array is already sorted, what is the best-case time complexity of standard Insertion Sort? State in Big-O notation.", ["o(n)"], split="dev")
add_case("GEN7_ALG_11", "Algorithm Design", "Which tree traversal visits the root node before visiting either the left or right subtrees?", ["preorder", "pre-order"], split="test")
add_case("GEN7_ALG_12", "Algorithm Design", "What is the maximum number of nodes in a binary tree of depth K (where root is depth 1)?", ["2^k - 1", "2^k-1"], split="test")
add_case("GEN7_ALG_13", "Algorithm Design", "Which algorithmic approach solves subproblems only once and stores their results in a table?", ["dynamic programming", "memoization"], split="test")

# 10. Contradiction Detection (13 cases)
add_case("GEN7_CONTR_01", "Contradiction Detection", "Premise 1: The database port is 5432. Premise 2: The database port is 3306. Is there a contradiction between these two premises? Answer Yes or No.", ["yes"], split="dev")
add_case("GEN7_CONTR_02", "Contradiction Detection", "Premise 1: Server A is located in Frankfurt. Premise 2: Server A is running Linux Mint. Is there a contradiction between these two premises? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_CONTR_03", "Contradiction Detection", "Premise 1: All users must verify their email. Premise 2: User #99 verified her email. Is there a contradiction? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_CONTR_04", "Contradiction Detection", "Premise 1: System auth is strictly passwordless. Premise 2: Users are required to enter an 8-character password. Is there a contradiction? Answer Yes or No.", ["yes"], split="dev")
add_case("GEN7_CONTR_05", "Contradiction Detection", "Premise 1: The car's fuel tank is completely empty. Premise 2: The car drove 100 miles on that fuel tank without refueling. Is there a contradiction? Answer Yes or No.", ["yes"], split="dev")
add_case("GEN7_CONTR_06", "Contradiction Detection", "Premise 1: The file is read-only. Premise 2: The process appended 5 lines to the file without changing permissions. Is there a contradiction? Answer Yes or No.", ["yes"], split="dev")
add_case("GEN7_CONTR_07", "Contradiction Detection", "Premise 1: John has two siblings: Alice and Bob. Premise 2: John is an only child. Is there a contradiction? Answer Yes or No.", ["yes"], split="dev")
add_case("GEN7_CONTR_08", "Contradiction Detection", "Premise 1: The room temperature is 22C. Premise 2: The room temperature is 71.6F. Is there a contradiction? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_CONTR_09", "Contradiction Detection", "Premise 1: Service X requires Python 3.12 or newer. Premise 2: Service X is successfully running in an environment with Python 3.8. Is there a contradiction? Answer Yes or No.", ["yes"], split="dev")
add_case("GEN7_CONTR_10", "Contradiction Detection", "Premise 1: The website is hosted on AWS us-east-1. Premise 2: The domain resolves to Cloudflare CDN. Is there an inherent logical contradiction? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_CONTR_11", "Contradiction Detection", "Premise 1: The polygon has 5 vertices. Premise 2: The polygon is a quadrilateral. Is there a contradiction? Answer Yes or No.", ["yes"], split="test")
add_case("GEN7_CONTR_12", "Contradiction Detection", "Premise 1: The disk partition is 100% full. Premise 2: A 2 GB file was created on that partition without errors. Is there a contradiction? Answer Yes or No.", ["yes"], split="test")
add_case("GEN7_CONTR_13", "Contradiction Detection", "Premise 1: Every cat is a mammal. Premise 2: No mammal is a reptile. Premise 3: Whiskers is a cat. Can Whiskers be a reptile? Answer Yes or No.", ["no"], split="test")

# 11. Planning Under Limited Resources (13 cases)
add_case("GEN7_PLR_01", "Planning Under Limited Resources", "You have $10 and need to buy lunch. A sandwich costs $6, an apple costs $2, and a soda costs $3. Can you buy all three items without exceeding your budget? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_PLR_02", "Planning Under Limited Resources", "A backup battery provides 120 minutes of runtime. Device A consumes 30W (needs 60 mins), Device B consumes 50W (needs 60 mins). Both cannot run simultaneously. If they run sequentially for 60 minutes each, will the battery last? Answer Yes or No.", ["yes"], split="dev")
add_case("GEN7_PLR_03", "Planning Under Limited Resources", "A USB drive has 4 GB free space. You need to copy 3 video files sized 1.2 GB, 1.5 GB, and 1.4 GB. Can all three files fit on the drive? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_PLR_04", "Planning Under Limited Resources", "A server has 8 GB RAM. The OS uses 2 GB. Can you concurrently run two worker processes that each allocate 3 GB RAM? Answer Yes or No.", ["yes"], split="dev")
add_case("GEN7_PLR_05", "Planning Under Limited Resources", "You have a 15-minute maintenance window. Task 1 takes 5 mins, Task 2 takes 6 mins, Task 3 takes 4 mins. Can all three tasks be completed within the window? Answer Yes or No.", ["yes"], split="dev")
add_case("GEN7_PLR_06", "Planning Under Limited Resources", "An elevator has a maximum weight limit of 500 kg. Can six adults weighing 90 kg each safely ride together without exceeding the limit? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_PLR_07", "Planning Under Limited Resources", "A cloud account has a spending limit of $50/month. Server A costs $25/mo, Server B costs $15/mo, and Database C costs $12/mo. Can all three resources be provisioned? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_PLR_08", "Planning Under Limited Resources", "A delivery van can carry at most 800 kg. Package 1 is 300 kg, Package 2 is 250 kg, Package 3 is 260 kg. Can the van carry all three in one trip? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_PLR_09", "Planning Under Limited Resources", "A CPU has 4 execution threads. Job A requires 2 threads, Job B requires 1 thread, Job C requires 1 thread. Can they all run concurrently? Answer Yes or No.", ["yes"], split="dev")
add_case("GEN7_PLR_10", "Planning Under Limited Resources", "A developer has 4 hours remaining in the workday. Task X requires 2.5 hours, Task Y requires 1.5 hours. Can both tasks be finished today? Answer Yes or No.", ["yes"], split="dev")
add_case("GEN7_PLR_11", "Planning Under Limited Resources", "A team has a sprint budget of 40 story points. Backlog items are 13, 8, 8, 5, and 8 points. What is the total points required, and does it fit within the 40-point budget? Answer Yes or No.", ["no", "42"], split="test")
add_case("GEN7_PLR_12", "Planning Under Limited Resources", "A mobile phone has 10% battery remaining and loses 3% per 10 minutes of GPS navigation. Can it complete a 40-minute drive on GPS? Answer Yes or No.", ["no"], split="test")
add_case("GEN7_PLR_13", "Planning Under Limited Resources", "A micro-instance has 1 vCPU and 1 GB RAM. Can it concurrently run a 2 GB database instance? Answer Yes or No.", ["no"], split="test")

# 12. Generalization to Unfamiliar Problems (14 cases)
add_case("GEN7_GEN_01", "Generalization to Unfamiliar Problems", "On planet Xylon, all 'zorks' are blue. A creature named Bleep is a zork. What color is Bleep?", ["blue"], split="dev")
add_case("GEN7_GEN_02", "Generalization to Unfamiliar Problems", "A fictional machine takes an input number, squares it, and subtracts 3. If the input is 5, what is the output?", ["22"], split="dev")
add_case("GEN7_GEN_03", "Generalization to Unfamiliar Problems", "In an alien language, 'mor' means big, 'rok' means stone, and 'morrok' means boulder. If 'fen' means tree, what would 'morfen' most likely mean?", ["big tree", "giant tree", "large tree"], split="dev")
add_case("GEN7_GEN_04", "Generalization to Unfamiliar Problems", "Rule: An object is 'glinting' if and only if it is metallic AND reflects light. Object Q is ceramic and reflects light. Is Object Q glinting? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_GEN_05", "Generalization to Unfamiliar Problems", "Suppose a custom clock has 8 hours in a day instead of 12. If the current time is 6:00 and 4 hours pass, what time does the clock show?", ["2:00", "2"], split="dev")
add_case("GEN7_GEN_06", "Generalization to Unfamiliar Problems", "In a fantasy board game, 3 copper coins equal 1 silver coin, and 4 silver coins equal 1 gold coin. How many copper coins equal 2 gold coins?", ["24"], split="dev")
add_case("GEN7_GEN_07", "Generalization to Unfamiliar Problems", "Operation '#' is defined as: a # b = (a * b) + a - b. Calculate 4 # 3.", ["13"], split="dev")
add_case("GEN7_GEN_08", "Generalization to Unfamiliar Problems", "On island Veritas, all birds fly backwards. An animal named Pippin is a bird on island Veritas. How does Pippin fly?", ["backwards", "backward"], split="dev")
add_case("GEN7_GEN_09", "Generalization to Unfamiliar Problems", "A synthetic cell divides into 3 daughter cells every hour. Starting with 1 cell, how many cells will exist after 2 hours?", ["9"], split="dev")
add_case("GEN7_GEN_10", "Generalization to Unfamiliar Problems", "In a new coding framework, syntax '@[x]' negates boolean x. What is the value of @[false]?", ["true"], split="dev")
add_case("GEN7_GEN_11", "Generalization to Unfamiliar Problems", "A fictional mineral 'Pyronite' glows green in darkness and blue in daylight. If Pyronite is observed inside a dark sealed cave, what color does it glow?", ["green"], split="test")
add_case("GEN7_GEN_12", "Generalization to Unfamiliar Problems", "Operation '@' is defined as: x @ y = (x + y) / 2. Calculate 10 @ 6.", ["8"], split="test")
add_case("GEN7_GEN_13", "Generalization to Unfamiliar Problems", "In a card game, Aces are worth 11, Kings are 10, and Queens are 10. What is the total point value of a hand with one Ace and two Queens?", ["31"], split="test")
add_case("GEN7_GEN_14", "Generalization to Unfamiliar Problems", "If a 'snark' is always hungry, and an entity is currently fully satisfied, can that entity be a snark? Answer Yes or No.", ["no"], split="test")

# 13. Multilingual Reasoning (13 cases)
add_case("GEN7_MLR_01", "Multilingual Reasoning", "Translate to English: 'Le ciel est bleu aujourd'hui.'", ["the sky is blue today"], split="dev")
add_case("GEN7_MLR_02", "Multilingual Reasoning", "In Spanish: 'El perro negro corre rápido.' What color is the dog according to this sentence? Answer in English.", ["black"], split="dev")
add_case("GEN7_MLR_03", "Multilingual Reasoning", "Translate to English: 'Guten Morgen, wie geht es Ihnen?'", ["good morning, how are you", "good morning, how are you doing"], split="dev")
add_case("GEN7_MLR_04", "Multilingual Reasoning", "In French: 'La voiture rouge est en panne.' What vehicle is broken down, and what color is it? Answer in English.", ["red car"], required_all=["red", "car"], split="dev")
add_case("GEN7_MLR_05", "Multilingual Reasoning", "In Italian: 'Tre più quattro fa sette.' What mathematical equation does this describe? Express using digits and standard operators.", ["3 + 4 = 7", "3+4=7"], split="dev")
add_case("GEN7_MLR_06", "Multilingual Reasoning", "Translate to English: 'Muchas gracias por su ayuda.'", ["thank you very much for your help", "thanks a lot for your help"], split="dev")
add_case("GEN7_MLR_07", "Multilingual Reasoning", "In German: 'Die Katze schläft auf dem Sofa.' Where is the cat sleeping? Answer in English.", ["sofa", "couch"], split="dev")
add_case("GEN7_MLR_08", "Multilingual Reasoning", "In Spanish: 'Hoy es lunes, mañana es martes.' What day of the week is tomorrow? Answer in English.", ["tuesday"], split="dev")
add_case("GEN7_MLR_09", "Multilingual Reasoning", "Translate to English: 'Je ne comprends pas la question.'", ["i do not understand the question", "i don't understand the question"], split="dev")
add_case("GEN7_MLR_10", "Multilingual Reasoning", "In Japanese romaji: 'Kore wa hon desu.' What object is being referred to? Answer in English.", ["book"], split="dev")
add_case("GEN7_MLR_11", "Multilingual Reasoning", "In French: 'Deux multiplié par cinq égale dix.' Write the mathematical expression with digits.", ["2 * 5 = 10", "2 x 5 = 10", "2*5=10"], split="test")
add_case("GEN7_MLR_12", "Multilingual Reasoning", "Translate to English: 'Das Wetter ist sehr kalt im Winter.'", ["the weather is very cold in winter", "the weather is very cold in the winter"], split="test")
add_case("GEN7_MLR_13", "Multilingual Reasoning", "In Spanish: 'La biblioteca está abierta hasta las ocho.' Until what time is the library open? Answer in English.", ["8", "8:00", "eight"], split="test")

# 14. Abstract Reasoning (13 cases)
add_case("GEN7_ABR_01", "Abstract Reasoning", "What is the next number in the pattern: 3, 6, 12, 24, ?", ["48"], split="dev")
add_case("GEN7_ABR_02", "Abstract Reasoning", "Analogy: Bird is to Nest as Bee is to what?", ["hive", "beehive"], split="dev")
add_case("GEN7_ABR_03", "Abstract Reasoning", "What letter comes next in the sequence: A, C, E, G, ?", ["i", "I"], split="dev")
add_case("GEN7_ABR_04", "Abstract Reasoning", "Analogy: Book is to Author as Painting is to what?", ["painter", "artist"], split="dev")
add_case("GEN7_ABR_05", "Abstract Reasoning", "Identify the next number in the sequence: 1, 4, 9, 16, 25, ?", ["36"], split="dev")
add_case("GEN7_ABR_06", "Abstract Reasoning", "Analogy: Engine is to Car as Heart is to what?", ["body", "human"], split="dev")
add_case("GEN7_ABR_07", "Abstract Reasoning", "What is the next term in the sequence: 100, 90, 80, 70, ?", ["60"], split="dev")
add_case("GEN7_ABR_08", "Abstract Reasoning", "Analogy: Water is to Thirst as Food is to what?", ["hunger"], split="dev")
add_case("GEN7_ABR_09", "Abstract Reasoning", "What is the next number in the sequence: 2, 3, 5, 7, 11, ?", ["13"], split="dev")
add_case("GEN7_ABR_10", "Abstract Reasoning", "Analogy: Clock is to Time as Thermometer is to what?", ["temperature"], split="dev")
add_case("GEN7_ABR_11", "Abstract Reasoning", "What letter comes next in the pattern: Z, X, V, T, ?", ["r", "R"], split="test")
add_case("GEN7_ABR_12", "Abstract Reasoning", "Analogy: Tree is to Leaf as Flower is to what?", ["petal"], split="test")
add_case("GEN7_ABR_13", "Abstract Reasoning", "What is the next number in the pattern: 5, 10, 20, 40, ?", ["80"], split="test")

# 15. Conditional Reasoning (14 cases)
add_case("GEN7_CND_01", "Conditional Reasoning", "If the user is an admin, grant access. If the user is a guest, deny access. User Sarah is an admin. Should access be granted or denied?", ["granted", "grant"], split="dev")
add_case("GEN7_CND_02", "Conditional Reasoning", "If temperature < 0C, water freezes. If temperature >= 100C, water boils. Otherwise, water is liquid. Temperature is 25C. What state is the water in?", ["liquid"], split="dev")
add_case("GEN7_CND_03", "Conditional Reasoning", "If order total > $100, shipping is free. Otherwise, shipping costs $10. Order total is $85. What is the shipping cost?", ["$10", "10"], split="dev")
add_case("GEN7_CND_04", "Conditional Reasoning", "If signal strength is above 3 bars, enable video streaming. Otherwise, use audio-only mode. Signal strength is 2 bars. Which mode should be used?", ["audio", "audio-only"], split="dev")
add_case("GEN7_CND_05", "Conditional Reasoning", "If customer is a VIP member OR purchase is over $500, apply 15% discount. Customer is NOT VIP, but purchase is $600. Does the discount apply? Answer Yes or No.", ["yes"], split="dev")
add_case("GEN7_CND_06", "Conditional Reasoning", "If disk space < 10% AND memory < 5%, trigger emergency alarm. Disk space is 8%, but memory is 40%. Is the emergency alarm triggered? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_CND_07", "Conditional Reasoning", "Rule: If day is Saturday OR Sunday, alarm is set to 09:00. On weekdays, alarm is set to 07:00. Today is Sunday. What time is the alarm set for?", ["09:00", "9:00", "9 am"], split="dev")
add_case("GEN7_CND_08", "Conditional Reasoning", "If score >= 90, grade is A. If 80 <= score < 90, grade is B. If 70 <= score < 80, grade is C. Student scored 82. What grade did the student receive?", ["b", "B"], split="dev")
add_case("GEN7_CND_09", "Conditional Reasoning", "If packet is marked urgent, send immediately. If packet is normal, buffer for 50ms. Packet #401 is normal. What action is taken?", ["buffer", "buffer for 50ms", "wait"], split="dev")
add_case("GEN7_CND_10", "Conditional Reasoning", "If door is closed AND locked, keycard is required. Door is closed but unlocked. Is a keycard required to enter? Answer Yes or No.", ["no"], split="dev")
add_case("GEN7_CND_11", "Conditional Reasoning", "If vehicle is electric, exempt from emissions test. Vehicle T is a hybrid with a gas engine. Is Vehicle T an electric-only vehicle under this rule? Answer Yes or No.", ["no"], split="test")
add_case("GEN7_CND_12", "Conditional Reasoning", "If license is expired OR penalty points > 12, suspend driver. Driver has valid license and 14 penalty points. Should the driver be suspended? Answer Yes or No.", ["yes"], split="test")
add_case("GEN7_CND_13", "Conditional Reasoning", "If humidity > 70% AND temp > 30C, trigger mold alert. Humidity is 85% and temp is 32C. Is the alert triggered? Answer Yes or No.", ["yes"], split="test")
add_case("GEN7_CND_14", "Conditional Reasoning", "If account age < 30 days, daily transfer limit is $500. Otherwise, limit is $5,000. Account was created 60 days ago. What is the daily transfer limit?", ["$5,000", "5000", "$5000"], split="test")

dev_cases = [c for c in cases if c["split"] == "dev"]
test_cases = [c for c in cases if c["split"] == "test"]

print(f"Total generated cases: {len(cases)}")
print(f"Dev split cases: {len(dev_cases)}")
print(f"Test split cases: {len(test_cases)}")

dataset = {
    "version": "7.0",
    "name": "Generalization Benchmark v7 (Held-Out)",
    "description": "200 unseen reasoning and generalization tasks across 15 categories, split into 160 dev and 40 test cases.",
    "total_cases": len(cases),
    "dev_count": len(dev_cases),
    "test_count": len(test_cases),
    "cases": cases,
    "dev_cases": dev_cases,
    "test_cases": test_cases
}

out_path = "benchmarks/datasets/generalization_benchmark_v7.json"
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w") as f:
    json.dump(dataset, f, indent=2)

print(f"Saved dataset to {out_path}")
