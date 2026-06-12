export function graphStorageKey(bookId: string, chapter: number) {
  return `lorevia:graph-layout:${bookId}:${chapter}`
}

export function graphLabelKey(bookId: string) {
  return `lorevia:graph-labels:${bookId}`
}

export function relationshipLabel(value: string | null | undefined) {
  return (value || "connection").replaceAll("_", " ")
}

const RELATIONSHIP_LABEL_TEXT: Record<string, string> = {
  best_friend: "best friend",
  childhood_friend: "childhood friend",
  former_friend: "former friend",
  secret_friend: "secret friend",
  loyal_friend: "loyal friend",
  protective_friend: "protective friend",
  jealous_friend: "jealous friend",
  one_sided_friend: "one-sided friend",
  manipulative_friend: "manipulative friend",
  fake_friend: "fake friend",
  enemy_turned_friend: "enemy-turned-friend",
  friend_turned_enemy: "friend-turned-enemy",
  friend_toxic: "friend (toxic)",
  friend_romantic: "friend (romantic)",
  friend_codependent: "friend (codependent)",
  friend_platonic: "friend (platonic)",
  friend_casual: "friend (casual)",
  friend_open: "friend (open)",
  drinking_buddy: "drinking buddy",
  travel_companion: "travel companion",
  online_friend: "online friend",
  pen_pal: "pen pal",
  social_circle_member: "social circle member",
  cousin_brother: "cousin (brother)",
  cousin_sister: "cousin (sister)",
  half_brother: "half-brother",
  half_sister: "half-sister",
  foster_parent: "foster parent",
  adopted_parent: "adopted parent",
  adopted_child: "adopted child",
  family_rival: "family rival",
  estranged_family: "estranged family",
  disowned_child: "disowned child",
  illegitimate_child: "illegitimate child",
  missing_relative: "missing relative",
  grandmother_maternal: "grandmother (maternal)",
  grandmother_paternal: "grandmother (paternal)",
  grandfather_maternal: "grandfather (maternal)",
  grandfather_paternal: "grandfather (paternal)",
  in_law: "in-law",
  father_in_law: "father-in-law",
  mother_in_law: "mother-in-law",
  brother_in_law: "brother-in-law",
  sister_in_law: "sister-in-law",
  mutual_crush: "mutual crush",
  unrequited_love: "unrequited love",
  secret_lover: "secret lover",
  ex_lover: "ex-lover",
  ex_partner: "ex-partner",
  affair_partner: "affair partner",
  forbidden_romance: "forbidden romance",
  arranged_marriage_partner: "arranged marriage partner",
  political_marriage_partner: "political marriage partner",
  casual_fling: "casual fling",
  friends_with_benefits: "friends-with-benefits",
  love_triangle_rival: "love triangle rival",
  romantic_rival: "romantic rival",
  toxic_lover: "toxic lover",
  obsessive_lover: "obsessive lover",
  protective_lover: "protective lover",
  business_partner: "business partner",
  pawn_tool: "pawn (tool)",
  double_agent: "double agent",
  right_hand_person: "right-hand person",
  co_founder: "co-founder",
  rival_colleague: "rival colleague",
  former_colleague: "former colleague",
  workplace_rival: "workplace rival",
  work_mentor: "work mentor",
  work_friend: "work friend",
  workplace_friend: "workplace friend",
  work_spouse: "work spouse",
  team_member: "team member",
}

export const PRIMARY_RELATIONSHIP_TYPE_OPTIONS = [
  "ally", "enemy", "family", "friend", "mentor", "neutral", "political", "rival", "romantic",
  "sibling", "brother", "sister", "half_brother", "half_sister", "spouse", "lover",
  "colleague", "boss", "employee", "leader", "master", "slave", "owner", "captor", "prisoner",
] as const

export const SHARED_RELATIONSHIP_LABEL_OPTIONS = [
  "friend", "friend_toxic", "friend_romantic", "friend_codependent", "friend_platonic",
  "friend_casual", "friend_open", "best_friend", "childhood_friend", "former_friend",
  "secret_friend", "loyal_friend", "protective_friend", "jealous_friend", "one_sided_friend",
  "manipulative_friend", "fake_friend", "enemy_turned_friend", "friend_turned_enemy",
  "confidant", "drinking_buddy", "travel_companion", "online_friend", "pen_pal",
  "social_circle_member", "roommate", "housemate", "spouse", "lover", "crush",
  "mutual_crush", "unrequited_love", "secret_lover", "ex_lover", "ex_partner",
  "boyfriend", "girlfriend", "fiance", "fiancee", "husband", "wife", "affair_partner",
  "forbidden_romance", "arranged_marriage_partner", "political_marriage_partner", "soulmate",
  "casual_fling", "friends_with_benefits", "love_triangle_rival", "romantic_rival",
  "toxic_lover", "obsessive_lover", "protective_lover", "enemy", "rival", "nemesis",
  "family_rival", "estranged_family", "colleague", "rival_colleague", "former_colleague",
  "workplace_rival", "work_friend", "workplace_friend", "work_spouse", "team_member",
  "teammate", "business_partner", "co_founder", "client", "customer", "patron", "sponsor",
  "benefactor", "debtor", "creditor",
] as const

export const DIRECTIONAL_RELATIONSHIP_LABEL_OPTIONS = [
  "father", "mother", "son", "daughter", "brother", "sister", "half_brother", "half_sister",
  "sibling", "cousin_brother", "cousin_sister", "stepfather", "stepmother", "stepsibling",
  "grandmother_maternal", "grandmother_paternal", "grandfather_maternal", "grandfather_paternal",
  "uncle", "aunt", "nephew", "niece", "in_law", "father_in_law", "mother_in_law",
  "brother_in_law", "sister_in_law", "godfather", "godmother", "guardian", "foster_parent",
  "adopted_parent", "adopted_child", "ancestor", "descendant", "heir", "disowned_child",
  "illegitimate_child", "missing_relative", "teacher", "student", "professor", "researcher",
  "mentor", "work_mentor", "apprentice", "protege", "boss", "employee", "manager", "assistant",
  "intern", "investor", "contractor", "consultant", "supervisor", "superior", "subordinate",
  "commander", "soldier", "ruler", "subject", "king", "queen", "prince", "princess", "lord",
  "lady", "servant", "leader", "master", "slave", "owner", "bodyguard", "blackmailer",
  "hostage", "handler", "asset", "informant", "spy", "mole", "double_agent", "puppet",
  "controller", "pawn_tool", "enforcer", "henchman", "right_hand_person", "captor", "prisoner",
  "doctor", "patient", "lawyer", "bully", "victim", "abuser", "survivor", "hunter",
] as const

export function relationshipFacetLabel(value: string | null | undefined) {
  if (!value) return "connection"
  return RELATIONSHIP_LABEL_TEXT[value] || relationshipLabel(value)
}

export function relationshipFacetSummary(labels: string[] | null | undefined, fallback?: string | null) {
  const cleaned = Array.from(new Set((labels ?? []).filter(Boolean)))
  if (cleaned.length === 0) return relationshipFacetLabel(fallback || "connection")
  return cleaned.slice(0, 5).map(relationshipFacetLabel).join(", ")
}

export function sentimentLabel(value: unknown) {
  if (typeof value !== "number" || Number.isNaN(value)) return null
  if (value >= 0.45) return "Strongly positive"
  if (value >= 0.15) return "Positive"
  if (value <= -0.45) return "Strongly tense"
  if (value <= -0.15) return "Tense"
  return "Mixed or neutral"
}

export function zoomPercentLabel(value: number) {
  return `${Math.round(value * 100)}%`
}

export function nodeInitial(name: string) {
  const trimmed = name.trim()
  return trimmed ? trimmed.charAt(0).toUpperCase() : "?"
}
