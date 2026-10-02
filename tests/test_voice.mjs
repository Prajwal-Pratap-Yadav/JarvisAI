import test from 'node:test';
import assert from 'node:assert/strict';
import {commandFromTranscript} from '../jarvis/frontend/voice.js';
test('wake phrase does not treat unrelated speech as commands',()=>{
  assert.equal(commandFromTranscript('please delete files',true),'');
  assert.equal(commandFromTranscript('Hey Jarvis, system status',true),'system status');
  assert.equal(commandFromTranscript('Jarvis',true),'');
  assert.equal(commandFromTranscript('  list files  ',false),'list files');
});
