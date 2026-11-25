---
title: Scaling Autonomous Coding Agents Across 15,000 Repositories
seo_title: iFood Scales AI Coding Agents Across 15k Repositories
meta_description: Discover how iFood engineered the Remote Agents Platform to run
  autonomous coding tasks across 15,000 repositories using GPT-5.6 Luna at scale.
social_hook: How do you run autonomous coding agents across 15,000 repositories without
  breaking the bank? iFood's engineering team shares the architecture behind their
  Remote Agents Platform.
slug: scaling-autonomous-coding-agents-across-15-000-repositories-647841
category: AI & Autonomy
seo_tags:
- AI Agents
- Autonomous Coding
- Software Engineering
- GPT-5.6 Luna
- Infrastructure
- DevSecOps
image_url: https://upload.wikimedia.org/wikipedia/commons/thumb/1/12/MQ-9_Reaper_UAV_%28cropped%29.jpg/1280px-MQ-9_Reaper_UAV_%28cropped%29.jpg
source_url: https://openai.com/business/customer-stories/ifood
published_at: Tue, 24 Nov 2026 00:00:00 GMT
reading_time: 7
executive_summary: Facing the immense challenge of managing 15,000 code repositories,
  iFood engineered an internal Remote Agents Platform that abstracts complex agentic
  workflows into simple REST API calls. Powered by GPT-5.6 Luna and isolated sandboxes,
  the system has successfully completed over 25,000 runs while doubling vulnerability
  remediation accuracy. This architectural blueprint demonstrates how enterprise organizations
  can transition from fragmented automation attempts to unified, cost-effective agentic
  operations.
key_takeaways:
- The Remote Agents Platform standardizes agentic tasks across 15,000 repositories
  using an internal REST API interface.
- Combining deterministic bookends (cloning, publishing) with stochastic agentic execution
  guarantees workflow predictability.
- Operating at scale yielded over 25,000 runs with an average inference cost of just
  US$0.04 per task.
- The integration of OpenAI’s Structured Outputs ensures automated, contract-compliant
  verification of agent success or failure.
article_url: articles/scaling-autonomous-coding-agents-across-15-000-repositories-647841.html
draft: false
posted_to_discord: true
---

<h2>The Architectural Bottleneck of Enterprise Scale</h2>
<p>Managing software lifecycles across massive enterprise ecosystems historically collided with a fundamental infrastructural ceiling. While individual engineering teams easily conceived automation use cases for single codebases, multiplying those routines across thousands of repositories introduced severe fragmentation. The core engineering bottleneck was never a lack of intelligence or capability within large language models; it was the absolute absence of a dedicated, scalable execution runtime. Without a centralized agentic layer, technical units repeatedly built redundant, brittle point solutions that failed to scale under production pressures.</p>
<p>To eliminate this systemic friction, iFood’s engineering organization designed the Remote Agents Platform, transforming complex software maintenance into straightforward API invocations. Rather than forcing product teams to master agent orchestration, the platform provides a unified REST interface that handles lifecycle management entirely behind the scenes. Developers simply submit prompts and environment parameters, while the platform provisions isolated infrastructure to execute the workload asynchronously. This architectural shift redefines how large engineering organizations approach routine maintenance, dependency patching, and large-scale code validation.</p>

<h2>Engineering Predictability Through Sandboxed Execution</h2>
<p>Operating autonomous agents across sensitive enterprise perimeters demands absolute containment and predictable execution pathways. The Remote Agents Platform achieves this by enforcing a strict architectural separation between deterministic scaffolding and stochastic model reasoning. Every workflow begins and ends with deterministic steps: cloning the repository, importing required agent capabilities, setting up working branches, publishing merge results, and archiving artifacts. These bookends require zero probabilistic intelligence, ensuring that environment setup and final integration operate with mechanical reliability.</p>
<blockquote class="editorial-pullquote">"Solving this for one repository is easy. The challenge is solving it at scale across all 15,000 repositories."</blockquote>
<p>Sandwiched securely between these deterministic anchors lies the agentic execution phase, operating inside isolated Ubuntu environments tailored to the organization's diverse technology stack. The runtime natively integrates essential toolchains spanning Python, Java, Kotlin, C#, TypeScript, Rust, and Go, alongside direct access to internal enterprise utilities like GitLab, Nexus, Docker, Snyk, Kubernetes, and AWS. By routing execution through this controlled sandbox, the platform guarantees that autonomous agents operate with the precise permissions and dependencies required to execute complex refactoring safely.</p>

<h2>Balancing Intelligence, Speed, and Economic Viability</h2>
<p>At a scale exceeding 25,000 completed runs and billions of tokens consumed, model selection transitions from a theoretical benchmark exercise into a strict economic constraint. The engineering team selected GPT-5.6 Luna after evaluating models on a strict triad of requirements: high reasoning intelligence, operational efficiency, and rapid execution speed. For an internal platform handling enterprise-wide workloads, maintaining an average inference cost of just US$0.04 per run is an essential architectural achievement that dictates long-term financial sustainability.</p>
<p>Furthermore, verifying the success of autonomous actions at scale presents an inherent operational hurdle. iFood resolved this by enforcing strict post-execution validation using OpenAI’s Structured Outputs, which mandates that every agent response conforms to a predefined programmatic contract. This verification layer automatically classifies operational outcomes as positive or negative without requiring human intervention, enabling the system to scale its throughput securely across thousands of concurrent repositories without sacrificing code integrity.</p>

<h2>Unlocking Asynchronous Productivity Across the Enterprise</h2>
<p>The true return on investment delivered by the Remote Agents Platform lies not merely in execution speed, but in the liberation of human engineering capital. Because tasks execute asynchronously within isolated sandboxes, developers are entirely freed from the cognitive burden of monitoring routine execution loops. Engineers routinely launch complex security fixes, performance profiling, and dependency upgrades while stepping into architectural reviews, delegating mechanical toil entirely to the platform.</p>
<p>This capability was decisively proven during the rollout of an internal security product designed to scan and remediate vulnerable dependencies across all 15,000 repositories. Following migration to the Remote Agents Platform, the accuracy of these automated security fixes more than doubled, while the absolute volume of resolved vulnerabilities surged. By treating agentic execution as foundational infrastructure rather than a novelty, the organization has established a repeatable blueprint for engineering productivity in the era of autonomous systems.</p>
