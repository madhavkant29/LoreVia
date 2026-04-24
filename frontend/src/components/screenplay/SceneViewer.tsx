'use client';

import React, { useState, useEffect } from 'react';
import { Scene, Dialogue, ScreenplayViewerSettings } from '@/types/screenplay';

interface SceneViewerProps {
  scenes: Scene[];
  settings: ScreenplayViewerSettings;
  onSettingsChange: (settings: ScreenplayViewerSettings) => void;
}

export default function SceneViewer({ scenes, settings, onSettingsChange }: SceneViewerProps) {
  const [currentSceneIndex, setCurrentSceneIndex] = useState(0);
  const [showStats, setShowStats] = useState(settings.show_statistics);

  const currentScene = scenes[currentSceneIndex];

  const formatSceneHeading = (scene: Scene) => {
    const prefix = scene.interior ? 'INT.' : scene.exterior ? 'EXT.' : '';
    const location = scene.location || '';
    const time = scene.time_of_day || '';
    const sceneNum = scene.scene_number ? ` #${scene.scene_number}#` : '';
    return `${prefix} ${location} - ${time}${sceneNum}`;
  };

  const getFontSizeClass = () => {
    switch (settings.font_size) {
      case 'small': return 'text-sm';
      case 'large': return 'text-lg';
      default: return 'text-base';
    }
  };

  const getThemeClass = () => {
    switch (settings.theme) {
      case 'dark': return 'bg-gray-900 text-gray-100';
      case 'sepia': return 'bg-amber-50 text-amber-900';
      default: return 'bg-white text-gray-900';
    }
  };

  const goToScene = (index: number) => {
    if (index >= 0 && index < scenes.length) {
      setCurrentSceneIndex(index);
    }
  };

  const nextScene = () => goToScene(currentSceneIndex + 1);
  const prevScene = () => goToScene(currentSceneIndex - 1);

  if (!currentScene) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-500">No scenes available</p>
      </div>
    );
  }

  return (
    <div className={`h-full flex flex-col ${getThemeClass()}`}>
      {/* Header */}
      <div className="border-b px-4 py-3 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <button
            onClick={prevScene}
            disabled={currentSceneIndex === 0}
            className="px-3 py-1 rounded bg-gray-200 hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            ← Previous
          </button>
          <span className="font-medium">
            Scene {currentSceneIndex + 1} of {scenes.length}
          </span>
          <button
            onClick={nextScene}
            disabled={currentSceneIndex === scenes.length - 1}
            className="px-3 py-1 rounded bg-gray-200 hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next →
          </button>
        </div>
        
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setShowStats(!showStats)}
            className="px-3 py-1 rounded bg-blue-500 text-white hover:bg-blue-600"
          >
            {showStats ? 'Hide' : 'Show'} Stats
          </button>
        </div>
      </div>

      <div className="flex-1 flex">
        {/* Scene Content */}
        <div className={`flex-1 p-6 ${getFontSizeClass()} overflow-auto`}>
          {/* Scene Heading */}
          <div className="mb-6">
            <h2 className="text-xl font-bold uppercase tracking-wider">
              {formatSceneHeading(currentScene)}
            </h2>
            {settings.show_scene_numbers && currentScene.scene_number && (
              <p className="text-sm text-gray-500 mt-1">Scene {currentScene.scene_number}</p>
            )}
          </div>

          {/* Action/Description */}
          {currentScene.description && (
            <div className="mb-6 whitespace-pre-wrap">
              {currentScene.description}
            </div>
          )}

          {/* Dialogue */}
          {currentScene.dialogue.map((dialogue, index) => (
            <div key={dialogue.id} className="mb-4">
              {/* Character Name */}
              <div className="text-center font-bold uppercase">
                {dialogue.character_name}
                {dialogue.character_extension && (
                  <span className="ml-2 font-normal">
                    ({dialogue.character_extension})
                  </span>
                )}
              </div>

              {/* Parenthetical */}
              {dialogue.parenthetical && (
                <div className="text-center text-gray-600 mx-auto max-w-md">
                  ({dialogue.parenthetical})
                </div>
              )}

              {/* Dialogue Text */}
              <div className="mx-auto max-w-md whitespace-pre-wrap">
                {dialogue.dialogue_text}
              </div>

              {/* Line Number */}
              {settings.show_line_numbers && (
                <div className="text-xs text-gray-400 text-right mt-1">
                  Line {dialogue.line_number + 1}
                </div>
              )}
            </div>
          ))}

          {/* Word Count */}
          {currentScene.word_count && (
            <div className="mt-8 pt-4 border-t text-sm text-gray-500">
              Words: {currentScene.word_count}
              {currentScene.page_number && ` • Page ${currentScene.page_number}`}
            </div>
          )}
        </div>

        {/* Statistics Panel */}
        {showStats && (
          <div className="w-80 border-l p-4 overflow-auto">
            <h3 className="font-bold mb-4">Scene Statistics</h3>
            
            <div className="space-y-3 text-sm">
              <div>
                <span className="font-medium">Scene:</span> {currentScene.number}
              </div>
              <div>
                <span className="font-medium">Type:</span>{' '}
                {currentScene.interior ? 'Interior' : currentScene.exterior ? 'Exterior' : 'Other'}
              </div>
              <div>
                <span className="font-medium">Location:</span> {currentScene.location || 'Unknown'}
              </div>
              <div>
                <span className="font-medium">Time:</span> {currentScene.time_of_day || 'Unknown'}
              </div>
              <div>
                <span className="font-medium">Characters:</span>{' '}
                {currentScene.dialogue.length > 0 
                  ? [...new Set(currentScene.dialogue.map(d => d.character_name))].join(', ')
                  : 'None'
                }
              </div>
              <div>
                <span className="font-medium">Dialogue Lines:</span> {currentScene.dialogue.length}
              </div>
              <div>
                <span className="font-medium">Words:</span> {currentScene.word_count || 0}
              </div>
              <div>
                <span className="font-medium">Est. Duration:</span>{' '}
                {currentScene.word_count 
                  ? `${Math.round(currentScene.word_count / 250)} min`
                  : 'Unknown'
                }
              </div>
            </div>

            {/* Character Breakdown */}
            {currentScene.dialogue.length > 0 && (
              <div className="mt-6">
                <h4 className="font-bold mb-2">Character Dialogue</h4>
                <div className="space-y-1 text-sm">
                  {[...new Set(currentScene.dialogue.map(d => d.character_name))].map(char => {
                    const charLines = currentScene.dialogue.filter(d => d.character_name === char);
                    return (
                      <div key={char}>
                        <span className="font-medium">{char}:</span> {charLines.length} lines
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Settings Bar */}
      <div className="border-t px-4 py-2 flex items-center justify-between text-sm">
        <div className="flex items-center space-x-4">
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={settings.show_line_numbers}
              onChange={(e) => onSettingsChange({
                ...settings,
                show_line_numbers: e.target.checked
              })}
            />
            <span>Line Numbers</span>
          </label>
          
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={settings.show_scene_numbers}
              onChange={(e) => onSettingsChange({
                ...settings,
                show_scene_numbers: e.target.checked
              })}
            />
            <span>Scene Numbers</span>
          </label>
        </div>

        <div className="flex items-center space-x-4">
          <select
            value={settings.font_size}
            onChange={(e) => onSettingsChange({
              ...settings,
              font_size: e.target.value as 'small' | 'medium' | 'large'
            })}
            className="px-2 py-1 border rounded"
          >
            <option value="small">Small</option>
            <option value="medium">Medium</option>
            <option value="large">Large</option>
          </select>

          <select
            value={settings.theme}
            onChange={(e) => onSettingsChange({
              ...settings,
              theme: e.target.value as 'light' | 'dark' | 'sepia'
            })}
            className="px-2 py-1 border rounded"
          >
            <option value="light">Light</option>
            <option value="dark">Dark</option>
            <option value="sepia">Sepia</option>
          </select>
        </div>
      </div>
    </div>
  );
}
