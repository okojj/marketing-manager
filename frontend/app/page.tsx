"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

type User = { id: number; name: string; email: string };
type BrandInput = { name: string; description: string; target_audience: string; tone: string };
type Brand = BrandInput & { id: number; created_at: string };
const empty: BrandInput = { name: "", description: "", target_audience: "", tone: "" };

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { ...options, cache: "no-store", headers: { "Content-Type": "application/json", ...options?.headers } });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(response.status === 401 ? "로그인이 만료되었습니다. 다시 로그인해 주세요." : typeof body.detail === "string" ? body.detail : "요청을 처리하지 못했습니다. 입력 내용을 확인하고 다시 시도해 주세요.");
  }
  return response.status === 204 ? undefined as T : response.json();
}

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [googleEnabled, setGoogleEnabled] = useState(false);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [form, setForm] = useState<BrandInput>(empty);
  const [deleting, setDeleting] = useState<Brand | null>(null);
  const editor = useRef<HTMLDialogElement>(null);
  const confirmation = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    async function load() {
      try {
        const config = await api<{ google_enabled: boolean }>("/auth/config");
        setGoogleEnabled(config.google_enabled);
        const response = await fetch("/api/auth/me", { cache: "no-store" });
        if (response.ok) {
          setUser(await response.json());
          setBrands(await api<Brand[]>("/brands"));
        } else if (response.status !== 401) { throw new Error("계정 정보를 불러오지 못했습니다. 잠시 후 새로고침해 주세요."); }
        const authError = new URLSearchParams(window.location.search).get("auth_error");
        if (authError) {
          setError(authError === "not_configured" ? "Google 로그인 연결을 준비 중입니다." : "Google 로그인이 완료되지 않았습니다. 다시 시도해 주세요.");
          window.history.replaceState({}, "", "/");
        }
      } catch (e) { setError(e instanceof Error ? e.message : "연결 오류가 발생했습니다."); }
      finally { setReady(true); }
    }
    void load();
  }, []);

  function openEditor(brand?: Brand) {
    setEditing(brand?.id ?? null);
    setForm(brand ? { name: brand.name, description: brand.description, target_audience: brand.target_audience, tone: brand.tone } : empty);
    setError(""); setNotice(""); editor.current?.showModal();
  }
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const saved = await api<Brand>(editing === null ? "/brands" : `/brands/${editing}`, { method: editing === null ? "POST" : "PUT", body: JSON.stringify(form) });
      setBrands(current => editing === null ? [saved, ...current] : current.map(b => b.id === saved.id ? saved : b));
      editor.current?.close(); setNotice("브랜드 정보를 저장했습니다.");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function remove() {
    if (!deleting) return;
    setBusy(true); setError("");
    try {
      await api(`/brands/${deleting.id}`, { method: "DELETE" });
      setBrands(current => current.filter(b => b.id !== deleting.id));
      confirmation.current?.close(); setDeleting(null); setNotice("브랜드를 삭제했습니다.");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function logout() {
    setBusy(true); setError("");
    try { await api("/auth/logout", { method: "POST" }); setUser(null); setBrands([]); setNotice(""); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  const loginAction = googleEnabled ? <a className="button primary" href="/api/auth/google/login">Google 계정으로 시작하기 <span aria-hidden="true">↗</span></a> : <button className="button primary" disabled>Google 로그인 준비 중</button>;

  return <>
    <a className="skip" href="#main">본문으로 이동</a>
    <header className="global-nav"><div className="nav-inner"><a className="wordmark" href="/">Marketing Manager<span className="wordmark-dot">.</span></a><span className="nav-caption">A little clarity. A bigger story.</span><span>PHASE 01</span></div></header>
    <div className="sub-nav"><div className="nav-inner"><strong>{user ? "내 워크스페이스" : "브랜드의 다음 이야기"}</strong>{user ? <button className="text-button" disabled={busy} onClick={logout}>로그아웃</button> : <a href="#how-it-works">서비스 알아보기 <span aria-hidden="true">⌄</span></a>}</div></div>
    <main id="main">
      {!ready ? <section className="hero"><p role="status">워크스페이스를 불러오고 있습니다.</p></section> : user ? <>
        <section className="workspace-head container"><p className="eyebrow">YOUR WORKSPACE</p><h1>{user.name}님의<br/><span>브랜드를 만나볼까요.</span></h1><div className="section-bottom"><p className="muted">브랜드의 목소리를 정리하면, 다음 이야기가 선명해집니다.</p><button className="button primary" onClick={() => openEditor()}>브랜드 추가 <span aria-hidden="true">＋</span></button></div></section>
        <section className="workspace-body"><div className="container"><div className="section-label"><h2>내 브랜드 <span className="muted">{brands.length}</span></h2><span className="caption">나만의 브랜드 컨텍스트</span></div>
          {error && <p className="message" role="alert">{error}</p>}{notice && <p className="message" role="status">{notice}</p>}
          {brands.length === 0 ? <div className="empty-state"><span className="empty-symbol" aria-hidden="true">＋</span><h2>좋은 마케팅의 시작은,<br/>브랜드를 아는 것.</h2><p>서비스 소개와 타깃, 말투를 등록해 주세요.<br/>이곳에 나만의 브랜드가 모입니다.</p><button className="button primary" onClick={() => openEditor()}>첫 브랜드 등록하기</button></div> : <div className="brand-grid">{brands.map((brand, index) => <article className="brand-card" key={brand.id}><div className={`brand-art art-${index % 2}`} aria-hidden="true"><span>{brand.name.slice(0, 1)}</span><small>BRAND {String(index + 1).padStart(2, "0")}</small></div><div className="card-content"><h3>{brand.name}</h3><p className="brand-description">{brand.description}</p><dl><dt>타깃</dt><dd>{brand.target_audience}</dd><dt>브랜드 톤</dt><dd>{brand.tone}</dd></dl><div className="card-actions"><button className="text-button" onClick={() => openEditor(brand)}>브랜드 편집 ↗</button><button className="text-button" aria-label={`${brand.name} 삭제`} onClick={() => { setDeleting(brand); setError(""); confirmation.current?.showModal(); }}>삭제</button></div></div></article>)}</div>}
        </div></section>
      </> : <>
        <section className="hero container"><p className="eyebrow">AI MARKETING MANAGER</p><h1>당신의 브랜드.<br/><span>더 선명한 이야기.</span></h1><p className="lead">브랜드를 이해하는 것에서 시작해,<br/>사람들에게 닿는 콘텐츠로.</p><div className="hero-action">{loginAction}</div><p className="caption muted">하나의 Google 계정으로 나만의 작업 공간을 시작하세요.</p>{!googleEnabled && <p className="setup-note">Google 계정 연결을 준비 중입니다. 설정이 완료되면 시작할 수 있어요.</p>}{error && <p role="alert" className="message">{error}</p>}
          <div className="brand-composition" aria-label="브랜드의 목소리, 타깃, 콘텐츠 방향을 하나로 모으는 작업 공간"><div className="composition-label">YOUR BRAND, IN FOCUS.</div><div className="composition-word">Hello,<br/><span>possibility.</span></div><div className="composition-footer"><span>브랜드의 목소리</span><span>타깃의 관심사</span><span>다음 콘텐츠</span></div></div>
        </section>
        <section className="dark-tile" id="how-it-works"><div className="container"><p className="eyebrow">START WITH YOUR BRAND</p><h2>많은 말보다,<br/>당신다운 한마디.</h2><p className="lead">무엇을 만드는지. 누구를 위한 것인지.<br/>브랜드의 가장 중요한 이야기를 한곳에 담으세요.</p><div className="feature-row"><div><span>01</span><h3>브랜드를 알려주세요.</h3><p>서비스의 가치와 설명을<br/>차근차근 정리하세요.</p></div><div><span>02</span><h3>고객을 그려보세요.</h3><p>누구에게 이야기할지,<br/>어떤 관심사를 가졌는지.</p></div><div><span>03</span><h3>목소리를 정하세요.</h3><p>친근하게, 전문적으로.<br/>언제나 브랜드다운 말투로.</p></div></div></div></section>
        <section className="next-tile container"><p className="eyebrow">WHAT COMES NEXT</p><h2>아이디어에서 콘텐츠로.<br/>한 걸음씩, 함께.</h2><p className="muted">AI 아이디어 제안, 채널별 콘텐츠 제작과 승인·게시는<br/>다음 단계에서 만나보실 수 있습니다.</p><span className="coming-soon">준비 중</span></section>
      </>}
    </main>
    <footer><div className="container"><strong>Marketing Manager.</strong><p>브랜드의 이야기를 위한 조용한 작업 공간.</p><div className="footer-bottom"><span>Phase 1 · 브랜드 워크스페이스</span><span>{user ? user.email : "Google 계정으로 안전하게 시작하세요."}</span></div></div></footer>
    <dialog ref={editor} aria-labelledby="editor-title" onCancel={event => { if (busy) event.preventDefault(); }}><form onSubmit={save}><div className="dialog-heading"><div><p className="eyebrow">BRAND CONTEXT</p><h2 id="editor-title">{editing === null ? "새로운 브랜드" : "브랜드 편집"}</h2></div><button type="button" className="close-button" disabled={busy} aria-label="닫기" onClick={() => editor.current?.close()}>×</button></div><p className="muted caption">이 정보는 앞으로 만들 콘텐츠의 기준이 됩니다.</p><fieldset disabled={busy}><label>브랜드 이름<input required autoFocus maxLength={200} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="예: Oceanview" /></label><label>서비스 소개<textarea required maxLength={5000} rows={4} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="어떤 가치를 제공하나요?" /></label><label>주요 타깃<textarea required maxLength={2000} rows={2} value={form.target_audience} onChange={e => setForm({ ...form, target_audience: e.target.value })} placeholder="예: 주말 여행을 계획하는 20–40대" /></label><label>브랜드 톤<input required maxLength={100} value={form.tone} onChange={e => setForm({ ...form, tone: e.target.value })} placeholder="예: 친근하고 감각적인, 정보 중심" /></label></fieldset>{error && <p role="alert" className="message">{error}</p>}<div className="dialog-actions"><button type="button" className="button secondary" disabled={busy} onClick={() => editor.current?.close()}>취소</button><button className="button primary" disabled={busy}>{busy ? "저장 중…" : "브랜드 저장"}</button></div></form></dialog>
    <dialog ref={confirmation} aria-labelledby="delete-title" onCancel={event => { if (busy) event.preventDefault(); }}><h2 id="delete-title">브랜드를 삭제할까요?</h2><p>“{deleting?.name}”의 브랜드 정보를 삭제합니다. 이 작업은 되돌릴 수 없습니다.</p>{error && <p role="alert" className="message">{error}</p>}<div className="dialog-actions"><button className="button secondary" disabled={busy} onClick={() => confirmation.current?.close()}>취소</button><button className="button primary" disabled={busy} onClick={remove}>{busy ? "삭제 중…" : "삭제하기"}</button></div></dialog>
  </>;
}
