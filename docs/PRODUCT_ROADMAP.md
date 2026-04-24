# SageMate Product Roadmap: AI-Native Knowledge Radar

## 1. Core Philosophy

### The Problem
- **Traditional**: "Manual organization" (folder/tagging) = "Internalization".
- **AI Era**: Manual sorting is "manual labor". It kills the desire to internalize when data volume grows.

### The Solution
- **Internalization ≠ Filing**. It is **Making Connections** and **Critical Thinking**.
- **Role Split**:
  - **AI**: Handles "Indexing" (Entities, Tags, Links, Vector Search).
  - **Human**: Handles "Confirmation" (Deciding which connections matter, resolving conflicts).

## 2. Product Positioning

| Dimension | Traditional (Obsidian/Notion) | SageMate (AI-Native) |
| :--- | :--- | :--- |
| **Metaphor** | Library / Warehouse (You find books) | **Personal Advisor / Radar (Books find you)** |
| **Interaction** | Search & Browse | **Context-Aware Injection & Review** |
| **Value** | Storage Efficiency | **Recall Efficiency ("Reminding you what you forgot")** |

## 3. Roadmap

### Phase 1: Passive Radar (The "Review Loop")
- **Goal**: AI auto-indexes, Human reviews.
- **Features**:
  - `Auto-Entity Extraction`: Identify people, concepts, tech stacks automatically.
  - `Link Suggestions`: "This note mentions 'Rust'. Link to existing 'Rust' entity?" -> User clicks 'Yes'.
  - `Conflict Detection`: "New note contradicts 'Concept X' saved 3 months ago." -> User reviews and reconciles.

### Phase 2: Active Radar (Context-Aware Injection)
- **Goal**: Knowledge finds the user during creation.
- **Features**:
  - `Editor Radar`: Sidebar shows "Related Notes" based on current draft context.
  - `Smart Paste`: When pasting a URL, suggest: "You have 2 similar notes. Merge?"

### Phase 3: Knowledge Graph Visualization
- **Goal**: Visualizing the "Brain".
- **Features**:
  - Interactive graph view.
  - "Orphan" detection (knowledge that isn't connected).
