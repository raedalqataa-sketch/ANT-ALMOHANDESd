import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { VillaGenerator } from './villa-generator';
import { newClientDraft } from '@/lib/client-requirements';

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers(); });
function mount() {
  const draft = newClientDraft(); draft.data.title = 'متطلبات عميل حقيقية'; draft.counts['bedroom'] = 3;
  const view = render(<VillaGenerator draft={draft} />);
  const frame = view.container.querySelector('iframe');
  if (!frame?.contentWindow) throw new Error('Engine iframe not mounted');
  const post = vi.spyOn(frame.contentWindow, 'postMessage'); fireEvent.load(frame);
  const lastCall = post.mock.calls.at(-1);
  if (!lastCall) throw new Error('No handshake sent');
  const nonce = lastCall[0].nonce;
  const send = (type: string, extra = {}, origin = location.origin, source = frame.contentWindow) => act(() => {
    window.dispatchEvent(new MessageEvent('message', { origin, source, data: { channel: 'ANT_VILLA_V1', nonce, type, ...extra } }));
  });
  return { ...view, frame, post, nonce, send, draft };
}
describe('Python frame handoff', () => {
  it('sends the actual draft only after a matching same-origin ready handshake', () => {
    const m = mount();
    m.send('READY', { engineVersion: '0.6.2-general' }, 'https://untrusted.invalid');
    m.send('READY', { engineVersion: '0.6.2-general' }, location.origin, window);
    m.send('READY', { engineVersion: '0.6.2-general', nonce: 'old-session' });
    expect(m.post.mock.calls.filter(call => call[0].type === 'DRAFT')).toHaveLength(0);
    m.send('READY', { engineVersion: '0.6.2-general' });
    expect(m.post).toHaveBeenLastCalledWith({ channel: 'ANT_VILLA_V1', nonce: m.nonce, type: 'DRAFT', draft: m.draft }, location.origin);
    expect(m.frame.getAttribute('src')).toBe('/villa-engine/generate/index.html?embedded=1');
  });
  it('does not label transfer as generation and reports blocked results accurately', () => {
    const m = mount(); m.send('IMPORTED', { roomCount: 3 });
    expect(screen.getByRole('status').textContent).toContain('لم يُنشأ مسقط بعد');
    m.send('RESULT', { candidates: [{ reviewable: false }] });
    expect(screen.getByRole('status').textContent).toContain('دون مقترح مجتاز');
    m.send('RESULT', { candidates: [{ reviewable: true }, { reviewable: false }] });
    expect(screen.getByRole('status').textContent).toContain('1 مقترحات قابلة للمراجعة');
    expect(screen.getByRole('status').textContent).toContain('لا اعتماد تنفيذي');
  });
  it('surfaces missing runtime/version failures without pretend success', () => {
    const m = mount(); m.send('READY', { engineVersion: 'unverified-version' });
    expect(screen.getByRole('alert').textContent).toContain('إصدار المحرك لا يطابق');
    m.send('ERROR', { error: 'ملف المحرك غير متاح' });
    expect(screen.getByRole('alert').textContent).toBe('ملف المحرك غير متاح');
    expect(m.post.mock.calls.some(call => call[0].type === 'DRAFT')).toBe(false);
  });
  it('times out a missing handshake and stops listeners on unmount', () => {
    vi.useFakeTimers(); const m = mount();
    act(() => vi.advanceTimersByTime(30001));
    expect(screen.getByRole('alert').textContent).toContain('لم يحدث توليد');
    m.unmount(); const calls = m.post.mock.calls.length;
    m.send('READY', { engineVersion: '0.6.2-general' });
    expect(m.post.mock.calls).toHaveLength(calls);
    expect(vi.getTimerCount()).toBe(0);
  });
});

