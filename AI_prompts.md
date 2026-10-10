# HW5 — AI Prompts Log

This file logs the prompts typed to the AI coding assistant during HW5, organized by problem.

---

## Problem 1: Vibe Coder Prompts

1. > I am going to do my hw5. I am going to give you problems and you will put one section for each problem. Problem 1: Vibe coder prompts. Create AI_prompts.md and keep it updated as i work. This file is the log of what i typed.

---

## Problem 2: Study the Campus Customs Database

1. > Problem 2: Study the Campus Customs database. Unzip the zip file so you have data/campus_customs.db. That file is the originla shop database. Tables include desk, tickets, inventory, pricing, vendors, leases, cash_acounts, payments, and invoices. Your tools will update the database as tickets get resolved. Make a copy of the database file called data/campus_customs_new.db and point my MCP server and backend at that working copy. Later problems update that working copy. Wait for my instructions on the server and backend. Keep campus_customs.db untouched so i can reset when i want to restart resolving the tickets. Open data/campus_customs.db and look through every table and its field. There are some rules of this shop. The field desk.date_today is "today" for the shop. Use this date to determine what is overdue. Vendor lead times come from the vendors table. A vendor will not ship new product while they still have an open unpaid invoice. Human approval is required for any payments. Points will be deducted if this is not done. If payment is made, make sure to update the relevant table. If there is not enough cash, the pay tool must refuse - no negative balances. Cash only goes out in this homework - we did not model revenue, so no money comes in. Before a full run to resolve the tickets, make sure to reset the database to the original values. Do not email customers or call real vendors. Drafts stay on the board. Use my portkey_api_key for ai calls. Use only gpt-6-luna through Portkey for every agent. I am going to build a multi-agent operations. So now, study the three open tickets so you see how they link to other tables. Start output/harness.md. For each table, list the fields and one short line on why that table matters for the agents. You will keep growing this harness file in later problems.

2. > use 5.6 luna

---

## Problem 3: Build the MCP Server

1. > Problem 3: Build the MCP server. Write an MCP server in mcp_server/ using FastMCP. It will talk to data/campus_customs_new.db. You do not need to connect or run it in this problem. Every agent in this homework uses the tools in this MCP server. You will add more tools to it later; for now write three tools you know you will need for the tickets in the database. Keep the names clear. Never invent any data, only use information in the database. In output/harness.md, list each of your three MCP tools. For every tool include: which table it read, which ticket it helps unlock (101, 102, or 103), and one sentence on why that tool is the right one for that ticket. Vague lines like "reads inventory" score low - tie the tool to the ticket. Also add a short mcp_server/readme.md file that explains what the mcp server is for, which database file it uses, and the three tools it has.

---

## Problem 4: Add the MCP Server to the Vibe Coder and Test Each Tool

1. > Problem 4: Add the MCP server to vibe coder and test each tool. Add the MCP server to this project so you can call the tools. Save the connection JSON text in .mcp.json at the project root. Test each of the three MCP tools. Save the evidence in output/mcp_smoke.json. For every tool include: the prompt i asked you, the tool name, the tool output (must match values in data/campus_customs_new.db)

---

## Problem 5: Build the Agent Team and Grow the MCP Tools

1. > Problem 5: Build the agent team and grow the MCP tools. Build the agentic team for Campus Customs using Pydanticai: Boss, Inventory, Accounting, Facilities, and Customer Service. Boss agent reads each ticket, decides who should work on it and make final calls. Inventory agent checks stock by SKU and size, spots shortfalls, and figures out which vendor can restock. Accounting agent watches cash and invoices, checks margins, and prepares payemnts or purchase orders for human approval. Facilities agent handles the shop space side (leases, rent, etc.), Customer Service agent drafts messages for customers.  So for these agents, you should include prompts, models, and agent loops so they can delegate work to each other with full connectivity. Put the agent prompts in backend/prompts/ - one file per agent. Put data types in backend/models.py, and the agent files under backend/ (your layout can vary as long as the five roles are clear). Use my portkey_api_key and 5.6 luna model for every agent. I already told you the shop rules that agent needs. Add tools the agents need to the MCP server so they can work on the open tickets. I think the async tool and the async queue are pretty good tools to add, so that i can track my agents. Shop facts come from the MCP server over data/campus_customs_new.db - do not invent a second shop-tools layer that bypasses MCP. Wire the agents so they append to output/audit_trail.json as they run: for each agent-loop step, record enough to audit later. Append to this file - do not wipe it each run. In output/harness.md, list each agent and each MCP tool (including ones you add in this problem) along with which table the tool uses. Also add a short safety section: the guardrails a real business would want when agents touch real customers and real money, plus limits that keep token use in check. Update mcp_server/readme.md so the tool list matches what you have now.

---

## Problem 6: Plan the Three Tickets

1. > Problem 6: Plan the three tickets. Before you wire the backend, write down what you expect the team to do on each open ticket. I expect the boss agent will first examine the ticket and then assign to relevant work agents. If needed, multiple work agents will work at the same time. Finally, the boss agent will review the result. Ok, Build output/desk_tickets.html - a page you can double-click with one tab per ticket (101, 102, 103). Also add empty Cash and Reflection tabs for later problems (leave them blank or with a short "coming later" note for now. On each ticket tab, fill an Expected section only (leave room for an Actual section i will fill after i run the agents.  For each ticket's Expected section, record my words below: I expect the boss agent will first examine the ticket and then make the judgment to assign the issue to relevant work agents. If needed, multiple work agents will work at the same time. And each agent don't need to wait for the other agent before starting the task. Finally, the boss agent will review the result. And I think the MCP tools needed are many, such as tickets, vendors, payment requests, drafts, work quene and so on. You can record and write down more words if needed. As for my plan, I will examine the agents performance after they resolve the three tickets.

---

## Problem 7: Backend Routes

1. > Problem 7: Backend routes. Your React frontend dashboard (the next problem) needs a backend it can call. In backend/main.py, use Fastapi and add routes that do the following: Return the three tickets and whether each is open or resolved. Take a ticket id and run your agent team on that ticket. Return recent agent events - what each agent said and which tools they used - so the board can refresh. Approve a payment or pruchase after a human clicks apprve (agents only prepare the pay; this route is what actually changes cash). Return the current checking balance from cash_accounts. Reset the database to the original values when you wannt to try a fresh run. From the backend/ folder, start the server with uvicorn main:app --reload --port 8000. This turns on your backend at http://localhost:8000 so the frontend dashboard can call those routes. In output/harness.md, list each route in one line (what url/ what it does).

---

## Problem 8: Agent Dashboard

1. > Problem 8: Agent dashboard. Build the frontend dashboard in frontend/ with react + vite + typesceript. The page should call the routes you built in Problem 7. At minimum the board should: list all three tickets, let you pick one ticket and start the agent team on it, show each agent and what they are saying / doing while the ticket runs, mark a ticket resolved when the run finishes, show a short summary of what each agent did on that ticket, let a human approve a pay or purchase when asked, show the checking balance (it should drop after an approved pay). Make the dashboard look good. Be creative with the layout and feel - this is a real desk people would want to sit at, so put thought into how it looks. I want to make the dashboard easy to use, with the appealing icons and easy-to-follow instructions for the users to use. Make the numbers very visible to the users as well. Tell the front end to talk to the backend at http://localhost:8000. On the backend, allow the vite page origin (usually http://localhost:5173) so the browser is allowed to call those routes. Start the board with: npm run dev. This opens the reach desk in your browser so you can pick tickets and watch agents. Write output/design.md with what you chose for the dashboard look (layout, how agents read differently, how resolved tickets and cash show up) and why - including the creative choices that make it feel special and something humans would actually enjoy using.

---

## Problem 9: Resolve the Tickets

1. > Problem 9: Resolve the tickets. Before testing the agents on a full run over the three tickets, reset the working database data/campus_customs_new.db again so you start clean. Note the starting checking balance. Then run all three tickets on the board (101, 102, 103) until each is resolved. Open output/desk_tickets.html from Problem 6. On each ticket lab, fill the Actual section from this run: which agents worked, what they delegated, and which tools they used. Keep my expected section so i can compare the two. On the Cash tab of the same output/dask_tickets.html, itemize the money: 1. Starting checking balance (after the reset) 2. For each ticket: how cash changed when that ticket resolved and why (which pay / purchase, dollar amount) 3. Ending checking balance - it must match cash_accounts in the working database. Wrong cash match loses points even if the board shows every ticket resolved. Also save: 1. output/resolved_tickets.json - for each ticket: id, final status, short outcome, what each agent contributed, and any human approvals. 2. output/resolved_board.html - a page i can double-click with a screenshot of your React board for each resolved ticket (101, 102, and 103). Append real runs to output/audit_trail.json. Finish output/harness.md so it covers tables, MCP tools, the five agents, API routes, the dashboard, and safety rules.

2. > Make the background to be white; and i want to make the signature place to be more prominent, it took me a long time to find it

3. > done

---

## Problem 10: Reflection

1. > Problem 10: Reflection. Open output/desk_tickets.html and fill the Reflection tab. Record my own words. I think the agents performed very well in terms of the accuracy of calculations and the observance of the process rules. For example, the boss agent assigned agents correctly and the cash balance moved accurately in ticket 101. The dashboard could have been more user-friendly because it took me some time to navigate. For each ticket, the process is implemented correctly. Accounting agent is involved in each of the ticket and the dashboard asks me to sign off on each of the payment. As for what would have been simpler as one agent with tools is that the execution process will be more linear and avoid handoff latency. For the new problems this agent team could solve, I think it can solve any purchase problems from the customers. For the new problems this agent team could not solve, please let me know what problems you couldn't solve and what additional agents and tools you would need. Tie every answer to this app and the three tickets you ran - use the ticket tabs and cash tab on the same page as your evidence. Generic AI essays without Custom Customs details will score low.

---

## Problem 11: Submit to GitHub

1. > Problem 11: Submit to GitHub. Push your code to a public GitHub repository so graders can clone it. Put the repo URL in output/github_url.txt. Do not push the real .env to the GitHub repo. Do include both database files under data/ (the original and your working copy) so graders can run your app easily. README should explain: copy original DB to the working copy when you need a clean run, start MCP server, start Fastapi backend, star the react board, reset the DB before a full three-ticket run. The file layout should be: AI_prompts.md, requirements.txt, .env.example, .gitignore, .mcp.json, README.md, data/campus_customs.db, campus_customs_new.db, mcp_server/, frontend/, backend/, output/

2. > https://github.com/Lc2000111/campus-custom-hw5
