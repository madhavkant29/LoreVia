// Screenplay-related types for LoreVia frontend

export interface Scene {
  id: string;
  book_id: string;
  chapter_id?: string;
  number: number;
  heading: string;
  location?: string;
  time_of_day?: string;
  interior: boolean;
  exterior: boolean;
  scene_number?: string;
  description?: string;
  word_count?: number;
  page_number?: number;
  created_at: string;
  dialogue: Dialogue[];
}

export interface Dialogue {
  id: string;
  scene_id: string;
  character_name: string;
  character_extension?: string;
  dialogue_text: string;
  parenthetical?: string;
  line_number: number;
  word_count?: number;
  created_at: string;
}

export interface ScreenplayStats {
  total_scenes: number;
  total_dialogue_lines: number;
  total_words: number;
  estimated_pages?: number;
  character_dialogue_counts: Record<string, number>;
  scene_types: {
    INT: number;
    EXT: number;
    OTHER: number;
  };
}

export interface SceneAnalysis {
  scene_number: number;
  scene_heading: string;
  characters_present: string[];
  dialogue_count: number;
  action_lines: number;
  estimated_duration_minutes?: number;
}

export interface ScreenplayImportResult {
  book_id: string;
  imported_scenes: number[];
  total_scenes: number;
  total_dialogue_lines: number;
  mode: string;
  source_kind: string;
}

export interface BookWithScreenplay {
  id: string;
  title: string;
  author?: string;
  genre?: string;
  format: string; // 'screenplay' | 'pdf' | 'epub'
  status: string;
  mode: string;
  source_kind: string;
  cover_url?: string;
  total_chapters?: number;
  total_tokens?: number;
  is_truncated: boolean;
  primary_series_id?: string;
  series_name?: string;
  series_order?: number;
  is_public: boolean;
  public_description?: string;
  copyright_warning: boolean;
  archived_at?: string;
  hidden_at?: string;
  created_at: string;
  progress_pct?: number;
  chapters_read_count?: number;
  chapters_left?: number;
  screenplay_stats?: ScreenplayStats;
}

export interface SceneFilter {
  type?: 'ALL' | 'INT' | 'EXT';
  character?: string;
  location?: string;
  search?: string;
}

export interface ScreenplayViewerSettings {
  show_line_numbers: boolean;
  show_scene_numbers: boolean;
  font_size: 'small' | 'medium' | 'large';
  theme: 'light' | 'dark' | 'sepia';
  show_statistics: boolean;
}
