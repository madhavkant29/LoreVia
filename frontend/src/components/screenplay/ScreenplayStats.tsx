'use client';

import React from 'react';
import type { ScreenplayStats } from '@/types/screenplay';

interface ScreenplayStatsProps {
  stats: ScreenplayStats;
}

export default function ScreenplayStats({ stats }: ScreenplayStatsProps) {
  const mostTalkativeCharacter = Object.entries(stats.character_dialogue_counts)
    .sort(([, a], [, b]) => b - a)[0];

  const sceneTypePercentage = (type: number) => {
    if (stats.total_scenes === 0) return 0;
    return Math.round((type / stats.total_scenes) * 100);
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border p-6">
      <h2 className="text-xl font-bold mb-4">Screenplay Statistics</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-blue-50 rounded p-4">
          <div className="text-2xl font-bold text-blue-600">{stats.total_scenes}</div>
          <div className="text-sm text-gray-600">Total Scenes</div>
        </div>
        
        <div className="bg-green-50 rounded p-4">
          <div className="text-2xl font-bold text-green-600">{stats.total_dialogue_lines}</div>
          <div className="text-sm text-gray-600">Dialogue Lines</div>
        </div>
        
        <div className="bg-purple-50 rounded p-4">
          <div className="text-2xl font-bold text-purple-600">{stats.total_words.toLocaleString()}</div>
          <div className="text-sm text-gray-600">Total Words</div>
        </div>
        
        <div className="bg-orange-50 rounded p-4">
          <div className="text-2xl font-bold text-orange-600">{stats.estimated_pages || 'N/A'}</div>
          <div className="text-sm text-gray-600">Est. Pages</div>
        </div>
      </div>

      {/* Scene Types */}
      <div className="mb-6">
        <h3 className="text-lg font-semibold mb-3">Scene Types</h3>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Interior (INT)</span>
            <div className="flex items-center space-x-2">
              <div className="w-32 bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-blue-500 h-2 rounded-full" 
                  style={{ width: `${sceneTypePercentage(stats.scene_types.INT)}%` }}
                />
              </div>
              <span className="text-sm text-gray-600 w-12 text-right">
                {stats.scene_types.INT} ({sceneTypePercentage(stats.scene_types.INT)}%)
              </span>
            </div>
          </div>
          
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Exterior (EXT)</span>
            <div className="flex items-center space-x-2">
              <div className="w-32 bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-green-500 h-2 rounded-full" 
                  style={{ width: `${sceneTypePercentage(stats.scene_types.EXT)}%` }}
                />
              </div>
              <span className="text-sm text-gray-600 w-12 text-right">
                {stats.scene_types.EXT} ({sceneTypePercentage(stats.scene_types.EXT)}%)
              </span>
            </div>
          </div>
          
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Other</span>
            <div className="flex items-center space-x-2">
              <div className="w-32 bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-gray-500 h-2 rounded-full" 
                  style={{ width: `${sceneTypePercentage(stats.scene_types.OTHER)}%` }}
                />
              </div>
              <span className="text-sm text-gray-600 w-12 text-right">
                {stats.scene_types.OTHER} ({sceneTypePercentage(stats.scene_types.OTHER)}%)
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Character Dialogue Counts */}
      <div className="mb-6">
        <h3 className="text-lg font-semibold mb-3">Character Dialogue</h3>
        <div className="space-y-2 max-h-64 overflow-auto">
          {Object.entries(stats.character_dialogue_counts)
            .sort(([, a], [, b]) => b - a)
            .map(([character, count]) => (
              <div key={character} className="flex items-center justify-between">
                <span className="text-sm font-medium">{character}</span>
                <div className="flex items-center space-x-2">
                  <div className="w-32 bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-purple-500 h-2 rounded-full" 
                      style={{ 
                        width: `${Math.round((count / stats.total_dialogue_lines) * 100)}%` 
                      }}
                    />
                  </div>
                  <span className="text-sm text-gray-600 w-12 text-right">
                    {count} ({Math.round((count / stats.total_dialogue_lines) * 100)}%)
                  </span>
                </div>
              </div>
            ))}
        </div>
      </div>

      {/* Key Insights */}
      <div className="bg-gray-50 rounded p-4">
        <h3 className="text-sm font-semibold mb-2">Key Insights</h3>
        <ul className="text-sm space-y-1 text-gray-600">
          <li>
            • Average words per scene: {stats.total_scenes > 0 ? Math.round(stats.total_words / stats.total_scenes) : 0}
          </li>
          <li>
            • Average dialogue per scene: {stats.total_scenes > 0 ? Math.round(stats.total_dialogue_lines / stats.total_scenes) : 0}
          </li>
          {mostTalkativeCharacter && (
            <li>
              • Most talkative character: {mostTalkativeCharacter[0]} ({mostTalkativeCharacter[1]} lines)
            </li>
          )}
          <li>
            • Scene type balance: {stats.scene_types.INT > stats.scene_types.EXT ? 'More interior scenes' : 'More exterior scenes'}
          </li>
        </ul>
      </div>
    </div>
  );
}
