North Star 🌟
An agentic AI platform for large tech enterprises to intelligently staff projects, accelerate onboarding, and build a real-time map of their engineering talent. Built for the FutureStack'25 Hackathon.

The Problem
In large product companies like Meta and Google, staffing critical projects is slow, onboarding new engineers takes weeks, and understanding the true skill set of a 10,000-person engineering org is nearly impossible. Skill data is often self-reported and quickly becomes stale.

The Solution
North Star acts as an intelligent co-pilot for engineering leadership. It uses an agentic RAG system to analyze vast amounts of internal project data, providing data-driven insights and automating complex workflows.

Core Features
staffing️ Strategic Staffing: Recommends the best-suited engineers for new projects by analyzing their proven, evidence-based skills.

🎓 Personalized Onboarding: Automatically generates custom learning plans for developers by comparing a new project's codebase with their past work, slashing time-to-productivity.

🔬 Continuous Skill Intelligence: Passively analyzes code commits and design documents to build a dynamic, real-time "Talent Graph" of the organization's true capabilities.

How It Works
The platform is built on a secure, multi-tenant RAG architecture. A planning agent deconstructs requests, and an execution agent retrieves context from project-specific knowledge bases to inform its analysis and actions, such as creating Jira epics or Confluence pages.

Getting Started
Clone the repository.

Create a .env file from the .env.example and add your API keys.

- Set `EMBED_DIM` to match the dense embedding model (defaults to 1024 for BGE-M3). All Qdrant collections must use this dimension.
- Qdrant collections follow the pattern `tenant__project`. Ensure keyword payload indexes exist for `tenant_id`, `project_id`, and `project_key` to keep hybrid filters fast. The backend auto-checks these during startup.

Run docker-compose up -d --build.# North-Star
An agentic AI platform for large tech enterprises to intelligently staff projects, accelerate onboarding, and build a real-time map of their engineering talent. Built for the FutureStack'25 Hackathon.
