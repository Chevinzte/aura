# AURA Project Context

## Project

AURA is an AI-powered aesthetic matching system that learns from a user's
belongings and evaluates how well new items fit their personal style.

The motivating problem is that people may like individual items but struggle
to understand whether those items form a cohesive aesthetic.

Example:
A user owns floral/pink/beige earrings, bracelets and wallets, but has a navy
blue water bottle that feels visually out of place.

AURA should help answer:

"Does this item fit my aesthetic?"

## Product Direction

The primary product is an Aesthetic Matcher.

Aesthetic Discovery is used as the onboarding experience.

AURA should NOT force users into one aesthetic label such as "coquette" or
"minimalist". A user's aesthetic should be represented as a combination of
visual preferences.

## MVP User Flow

1. User starts AURA through Telegram.
2. User uploads approximately 5-10 belongings they like.
3. AURA analyses each item's visual characteristics.
4. AURA builds the user's aesthetic profile.
5. User uploads an item they own or are considering buying.
6. AURA compares the candidate item against their aesthetic profile.
7. AURA returns an explainable compatibility assessment.
8. User can provide feedback such as like/dislike.
9. Feedback can eventually improve the user's aesthetic profile.

## MVP Interface

Telegram Bot.

Do NOT couple business logic to Telegram.

Telegram should act as a client of the backend so that a web/mobile frontend
can be added later without rewriting the core application.

Future architecture:

Telegram ─┐
          ├── FastAPI Backend ── Supabase
Web App ──┘

## Technology Stack

Language: Python

Backend:
- FastAPI

MVP Frontend:
- Telegram Bot API

Database:
- Supabase PostgreSQL

Image Storage:
- Supabase Storage

Authentication for MVP:
- Telegram user ID

Potential future authentication:
- Supabase Auth

Potential vector storage:
- pgvector through Supabase/PostgreSQL

AI/Vision implementation:
- NOT DECIDED YET

Deployment:
- NOT DECIDED YET

## Proposed Repository Structure

aura/
├── backend/
├── telegram-bot/
├── ai/
├── docs/
├── .env.example
├── .gitignore
├── docker-compose.yml
└── README.md

## Core Domain Model

### User

Represents an AURA user.

Possible fields:

- id: UUID
- telegram_user_id: BIGINT, unique
- display_name
- onboarding_complete
- created_at

For the Telegram MVP, Telegram identity is sufficient.
Do not introduce Supabase Auth unless needed.

### Item

Represents an object uploaded by the user.

Examples:
- earrings
- bracelet
- wallet
- water bottle
- bag
- clothing

Possible fields:

- item_id
- user_id
- image_url
- item_type
- item_name
- source
- created_at

Possible source values:

OWNED
CANDIDATE

OWNED means the item contributes to understanding the user's aesthetic.

CANDIDATE means the item is being evaluated and should not automatically
change the user's aesthetic.

### ItemVisualFeatures

AI-generated visual analysis of an item.

Potential features:

- primary_colours
- patterns
- materials
- style_traits
- aesthetic_tags
- embedding
- ai_description

Example:

{
  "primaryColours": ["blush pink", "cream"],
  "patterns": ["floral"],
  "materials": ["gold metal"],
  "styleTraits": ["delicate", "feminine", "romantic"],
  "aestheticTags": {
    "soft_feminine": 0.88,
    "cottagecore": 0.61,
    "minimalist": 0.20
  }
}

The exact AI representation has NOT been finalized.

## Aesthetic Profile

Aggregated representation of the user's preferences.

Potential data:

- dominant_colours
- secondary_colours
- preferred_patterns
- preferred_materials
- style_traits
- aesthetic_tags
- profile_embedding
- generated_description
- updated_at

Example concept:

{
  "dominantColours": ["blush pink", "beige", "cream"],
  "preferredPatterns": ["floral"],
  "styleTraits": ["soft", "delicate", "feminine"]
}

The profile should be multidimensional rather than assigning one aesthetic.

## Match Analysis

Represents the comparison between a candidate item and the user's aesthetic.

Potential fields:

- analysis_id
- user_id
- candidate_item_id
- profile_id
- overall_score
- colour_score
- style_score
- pattern_score
- explanation
- recommendation
- created_at

Scores should NOT be presented as objective scientific measures.

The UI may instead communicate results such as:

Strong Fit
Moderate Fit
Intentional Contrast
Weak Fit

The explanation is more important than the numerical score.

## Feedback

Users should eventually be able to tell AURA whether its assessment reflects
their preferences.

Potential feedback:

LIKE
DISLIKE
BOUGHT
NOT_BOUGHT

This data may eventually allow AURA to learn preferences such as:

"The user generally prefers soft neutral colours but likes one bold contrasting
accessory."

## Product Principles

1. Personal aesthetic is subjective.
2. Do not treat aesthetic compatibility as objective truth.
3. Explain WHY an item matches or contrasts.
4. Do not force users into one aesthetic category.
5. Allow intentional contrast.
6. User feedback should eventually influence recommendations.
7. Keep Telegram separate from core business logic.
8. Design the backend so another frontend can be added later.

## Out of Scope for Initial MVP

Do NOT initially build:

- product recommendation marketplace
- shopping catalogue
- retailer integrations
- web scraping
- outfit generation
- full digital wardrobe
- complex ML recommendation system
- web/mobile frontend

The MVP should prove one core interaction:

"Learn what I like, then tell me whether this new item fits me."

## Major Open Question

The next major architectural decision is the AI pipeline:

Image
→ visual feature extraction
→ aesthetic representation
→ user profile aggregation
→ candidate/profile comparison
→ explainable recommendation

We have NOT yet selected the vision model, embedding model, scoring algorithm,
or exact matching methodology.

Do not make those choices implicitly. They should be designed explicitly
before implementation.