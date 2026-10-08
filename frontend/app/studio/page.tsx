"use client";
import { FormEvent, useEffect, useRef, useState } from "react";

type Channel = "blog" | "instagram" | "linkedin";
const labels: Record<Channel, string> = { blog: "블로그", instagram: "Instagram", linkedin: "LinkedIn" };
type Brief = { topic: string; goal: string; keywords: string; direction: string; channels: Channel[] };
type Brand = { id: number; name: string; description: string; tone: string; target_audience: string };
type Idea = { title: string; angle: string; rationale: string };
type Batch = { id: number; input: Brief; result: { ideas: Idea[] } | null; error: string | null; created_at: string };
type Content = { id: number; channel: Channel; title: string; body: string; revision: number };
type Campaign = { id: number; title: string; goal: string; brief: string; keywords: string; channels: Channel[]; contents: Content[]; created_at: string };
type Revision = { revision: number; title: string; body: string; source: string; created_at: string };
class ApiError extends Error { constructor(message: string, public status: number) { super(message); } }
async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { ...options, cache: "no-store", headers: { "Content-Type": "application/json", ...options?.headers } });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status === 401 ? "로그인이 만료되었습니다. 워크스페이스에서 다시 로그인해 주세요." : typeof body.detail === "string" ? body.detail : "입력 내용을 확인하고 다시 시도해 주세요.", response.status);
  }
  return response.json();
}
const initial: Brief = { topic: "", goal: "브랜드 인지도 높이기", keywords: "", direction: "", channels: ["blog", "instagram"] };

export default function Studio() {
  const [brand, setBrand] = useState<Brand | null>(null);
  const [brief, setBrief] = useState<Brief>(initial);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [ai, setAi] = useState({ provider: "", model: "" });
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [section, setSection] = useState<"ideas" | "campaigns">("ideas");
  const [editing, setEditing] = useState<Content | null>(null);
  const [text, setText] = useState({ title: "", body: "" });
  const [history, setHistory] = useState<Revision[]>([]);
  const editor = useRef<HTMLDialogElement>(null);
  const pending = useRef<{ payload: string; key: string } | null>(null);
  const campaign = campaigns.find(c => c.id === selected);
  const dirty = !!editing && (editing.title !== text.title || editing.body !== text.body);

  useEffect(() => {
    async function load() {
      try {
        const id = Number(new URLSearchParams(window.location.search).get("brand"));
        if (!Number.isInteger(id) || id <= 0) throw new Error("워크스페이스에서 브랜드를 선택해 주세요.");
        const [brandData, config, ideaData, campaignData] = await Promise.all([
          api<Brand>(`/brands/${id}`), api<{ enabled: boolean; provider: string; model: string }>("/ai/config"),
          api<Batch[]>(`/brands/${id}/ideas`), api<Campaign[]>(`/brands/${id}/campaigns`),
        ]);
        setBrand(brandData); setEnabled(config.enabled); setAi(config); setBatches(ideaData); setCampaigns(campaignData);
        if (campaignData.length) { setSelected(campaignData[0].id); setSection("campaigns"); }
      } catch (e) { setError((e as Error).message); }
      finally { setReady(true); }
    }
    void load();
  }, []);
  useEffect(() => {
    const prevent = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    if (dirty || busy) window.addEventListener("beforeunload", prevent);
    return () => window.removeEventListener("beforeunload", prevent);
  }, [dirty, busy]);

  async function getIdeas(event: FormEvent) {
    event.preventDefault(); if (!brand || busy) return;
    setBusy("ideas"); setError(""); setNotice("");
    const payload = JSON.stringify(brief);
    if (pending.current?.payload !== payload) pending.current = { payload, key: crypto.randomUUID() };
    try {
      const result = await api<Batch>(`/brands/${brand.id}/ideas`, { method: "POST", body: JSON.stringify({ ...brief, request_key: pending.current.key }) });
      setBatches(current => [result, ...current.filter(b => b.id !== result.id)]); pending.current = null;
      setNotice("아이디어 3개를 저장했습니다. 마음에 드는 방향으로 캠페인을 시작하세요.");
    } catch (e) {
      setError((e as Error).message);
      if (e instanceof ApiError && e.status !== 409) pending.current = null;
    } finally { setBusy(""); }
  }
  function updateCampaign(updated: Campaign) {
    setCampaigns(current => [updated, ...current.filter(c => c.id !== updated.id)]); setSelected(updated.id);
  }
  async function createCampaign(batch?: Batch, index?: number) {
    if (!brand || busy) return;
    const idea = batch?.result?.ideas[index ?? 0];
    const source = batch?.input ?? brief;
    if (!source.topic.trim() || !source.goal.trim() || !source.channels.length) {
      setError("주제, 목표와 채널을 입력해 주세요."); return;
    }
    setBusy("create"); setError(""); setNotice("");
    try {
      const result = await api<Campaign>(`/brands/${brand.id}/campaigns`, { method: "POST", body: JSON.stringify({
        topic: source.topic, goal: source.goal, keywords: source.keywords, channels: source.channels,
        title: idea?.title ?? source.topic.slice(0, 200),
        direction: idea ? idea.angle : source.direction,
        source_generation_id: batch?.id ?? null, idea_index: index ?? null,
      }) });
      updateCampaign(result); setSection("campaigns"); setNotice("캠페인을 저장했습니다. 채널별 초안을 만들어 보세요.");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(""); }
  }
  async function generate() {
    if (!campaign || busy) return;
    setBusy("drafts"); setError(""); setNotice("");
    const payload = `campaign:${campaign.id}`;
    if (pending.current?.payload !== payload) pending.current = { payload, key: crypto.randomUUID() };
    try {
      updateCampaign(await api<Campaign>(`/campaigns/${campaign.id}/generate`, { method: "POST", body: JSON.stringify({ request_key: pending.current.key }) }));
      pending.current = null; setNotice("초안을 저장했습니다. 사실관계와 표현을 검토해 주세요.");
    } catch (e) {
      setError((e as Error).message);
      if (e instanceof ApiError && e.status !== 409) pending.current = null;
    } finally { setBusy(""); }
  }
  function openEditor(content: Content) {
    setEditing(content); setText({ title: content.title, body: content.body }); setHistory([]); setError(""); editor.current?.showModal();
  }
  function closeEditor() {
    if (busy || (dirty && !window.confirm("저장하지 않은 수정 내용을 버릴까요?"))) return;
    editor.current?.close(); setEditing(null); setHistory([]);
  }
  async function save(event: FormEvent) {
    event.preventDefault(); if (!editing || !campaign) return;
    setBusy("save"); setError("");
    try {
      const saved = await api<Content>(`/contents/${editing.id}`, { method: "PUT", body: JSON.stringify({ ...text, revision: editing.revision }) });
      updateCampaign({ ...campaign, contents: campaign.contents.map(c => c.id === saved.id ? saved : c) });
      setEditing(null); editor.current?.close(); setNotice(`수정본 v${saved.revision}을 저장했습니다.`);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(""); }
  }
  async function revisions() {
    if (!editing) return;
    setBusy("history"); setError("");
    try { setHistory(await api<Revision[]>(`/contents/${editing.id}/revisions`)); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(""); }
  }
  async function refresh() {
    if (!brand || busy) return;
    setBusy("refresh"); setError("");
    try {
      const [items, ideas] = await Promise.all([api<Campaign[]>(`/brands/${brand.id}/campaigns`), api<Batch[]>(`/brands/${brand.id}/ideas`)]);
      setCampaigns(items); setBatches(ideas); setNotice("저장된 최신 내용을 불러왔습니다.");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(""); }
  }
  async function copy(content: Content) {
    try { await navigator.clipboard.writeText(`${content.title}\n\n${content.body}`); setNotice("콘텐츠를 복사했습니다."); }
    catch { setError("복사하지 못했습니다. 편집 화면에서 텍스트를 선택해 복사해 주세요."); }
  }

  return <>
    <a className="skip" href="#main">본문으로 이동</a>
    <header className="global-nav"><div className="nav-inner"><a className="wordmark" href="/">Marketing Manager.</a><span>CONTENT STUDIO</span></div></header>
    <div className="sub-nav"><div className="nav-inner"><strong>{brand?.name ?? "콘텐츠 스튜디오"}</strong><a href="/">워크스페이스로 돌아가기</a></div></div>
    <main id="main">
      <section className="workspace-head container"><p className="eyebrow">FROM IDEA TO STORY</p><h1>아이디어를 발견하고.<br/><span>이야기로 완성하세요.</span></h1><p className="muted">브랜드의 목소리로, 채널에 맞는 한 편의 콘텐츠.</p>
        {brand && <div className="brand-context-strip"><span>브랜드 톤 · {brand.tone}</span><span>타깃 · {brand.target_audience}</span></div>}
      </section>
      <section className="studio-body"><div className="container">
        {!ready ? <p role="status">스튜디오를 불러오고 있습니다.</p> : !brand ? <p role="alert" className="message">{error}</p> : <>
          <div className="studio-nav"><div className="segmented" aria-label="작업 선택"><button aria-pressed={section === "ideas"} disabled={!!busy} onClick={() => setSection("ideas")}>아이디어</button><button aria-pressed={section === "campaigns"} disabled={!!busy} onClick={() => setSection("campaigns")}>캠페인 {campaigns.length}</button></div><button className="text-button" disabled={!!busy} onClick={refresh}>저장 내역 새로고침 ↻</button></div>
          {!enabled && <p className="message">AI 연결을 준비 중입니다. 지금은 캠페인을 직접 작성하고 저장할 수 있습니다.</p>}
          {error && !editing && <p role="alert" className="message">{error}</p>}{notice && <p role="status" className="message">{notice}</p>}
          {(busy === "ideas" || busy === "drafts") && <p role="status" className="generation-status"><span className="pulse"/>브랜드 정보를 바탕으로 {busy === "ideas" ? "아이디어" : "채널별 초안"}를 만들고 있습니다. 잠시 기다려 주세요.</p>}
          {section === "ideas" ? <div className="idea-layout">
            <form className="brief-panel" onSubmit={getIdeas}><p className="eyebrow">01 · CREATIVE BRIEF</p><h2>어떤 이야기를<br/>전하고 싶나요?</h2><fieldset disabled={!!busy}>
              <label>주제<input required maxLength={500} value={brief.topic} onChange={e => setBrief({ ...brief, topic: e.target.value })} placeholder="예: 가을 주말 여행" /></label>
              <label>목표<input required maxLength={500} value={brief.goal} onChange={e => setBrief({ ...brief, goal: e.target.value })} /></label>
              <label>키워드 <span className="muted">선택</span><input maxLength={500} value={brief.keywords} onChange={e => setBrief({ ...brief, keywords: e.target.value })} placeholder="예: 오션뷰, 주말여행, 휴식" /></label>
              <label>콘텐츠 방향 <span className="muted">선택</span><textarea maxLength={2000} rows={3} value={brief.direction} onChange={e => setBrief({ ...brief, direction: e.target.value })} placeholder="강조할 내용이나 피하고 싶은 표현" /></label>
              <fieldset className="channel-picker"><legend>제작할 채널</legend>{(Object.keys(labels) as Channel[]).map(channel => <label key={channel}><input type="checkbox" checked={brief.channels.includes(channel)} onChange={e => setBrief({ ...brief, channels: e.target.checked ? [...brief.channels, channel] : brief.channels.filter(c => c !== channel) })} />{labels[channel]}</label>)}</fieldset>
            </fieldset><div className="brief-actions"><button className="button primary" disabled={!enabled || !!busy || !brief.channels.length}>{busy === "ideas" ? "아이디어 생성 중…" : "AI 아이디어 3개 제안받기"}</button><button type="button" className="text-button" disabled={!!busy} onClick={() => createCampaign()}>직접 캠페인으로 저장 ↗</button></div><p className="caption muted">{enabled ? `${ai.provider === "ollama" ? "Ollama" : "OpenAI"} · ${ai.model}. ` : ""}생성 시 브랜드 정보와 입력 내용이 {ai.provider === "ollama" ? "설정된 Ollama 서버" : "AI 공급자"}에 전달됩니다.</p></form>
            <div className="idea-results"><p className="eyebrow">02 · FIND YOUR ANGLE</p><h2>다음 이야기의 시작.</h2>{!batches.length ? <div className="studio-empty"><span aria-hidden="true">✦</span><h3>아직 쓰지 않은 이야기가 있어요.</h3><p>주제와 방향을 입력하면 브랜드에 맞는<br/>세 가지 아이디어를 제안합니다.</p></div> : batches.map(batch => <section className="idea-batch" key={batch.id}><div className="batch-heading"><strong>{batch.input.topic}</strong><small>{new Date(batch.created_at + "Z").toLocaleDateString("ko-KR")}</small></div>{batch.error ? <p className="message">{batch.error}</p> : batch.result?.ideas.map((idea, index) => <article className="idea-card" key={index}><span className="caption muted">IDEA {String(index + 1).padStart(2, "0")}</span><h3>{idea.title}</h3><p>{idea.angle}</p><p className="caption muted">{idea.rationale}</p><button className="text-button" disabled={!!busy} onClick={() => createCampaign(batch, index)}>이 아이디어로 캠페인 만들기 ↗</button></article>)}</section>)}</div>
          </div> : <div className="campaign-layout">
            <aside className="campaign-sidebar"><p className="eyebrow">MY CAMPAIGNS</p>{campaigns.map(c => <button key={c.id} disabled={!!busy} aria-pressed={selected === c.id} className="campaign-select" onClick={() => { setSelected(c.id); setError(""); setNotice(""); }}><strong>{c.title}</strong><span>{c.channels.map(ch => labels[ch]).join(" · ")}</span><small>{c.contents.length ? `${c.contents.length}개의 초안` : "기획 저장됨"}</small></button>)}<button className="text-button" disabled={!!busy} onClick={() => setSection("ideas")}>새 캠페인 시작 ＋</button></aside>
            <div className="campaign-detail">{!campaign ? <div className="studio-empty"><h2>첫 캠페인을 시작하세요.</h2><p>아이디어를 선택하거나 직접 기획을 작성해 보세요.</p><button className="button primary" onClick={() => setSection("ideas")}>아이디어 만들기</button></div> : <><p className="eyebrow">CAMPAIGN BRIEF</p><h2>{campaign.title}</h2><p className="muted">{campaign.goal}</p><details className="campaign-brief"><summary>기획 내용 보기</summary><p>{campaign.brief}</p><p>키워드: {campaign.keywords || "지정하지 않음"}</p><p className="caption muted">캠페인 생성 시점의 브랜드 정보를 기준으로 작성합니다.</p></details><div className="channel-badges">{campaign.channels.map(c => <span key={c}>{labels[c]}</span>)}</div>
              {!campaign.contents.length ? <div className="draft-start"><h3>이제, 채널에 맞는 이야기로.</h3><p>선택한 채널별로 초안을 한 편씩 작성합니다.</p><button className="button primary" disabled={!enabled || !!busy} onClick={generate}>{busy === "drafts" ? "초안 작성 중…" : "채널별 초안 생성"}</button></div> : <><p className="caption muted">AI가 작성한 초안입니다. 사실관계와 표현을 검토해 주세요. 아직 게시되지 않았습니다.</p>{campaign.contents.map(content => <article className="content-card" key={content.id}><div className="content-meta"><span>{labels[content.channel]} · 초안</span><span>v{content.revision}</span></div><h3>{content.title}</h3><div className="content-body">{content.body}</div><div className="card-actions"><button className="text-button" disabled={!!busy} onClick={() => openEditor(content)}>수정 및 이력 보기 ↗</button><button className="text-button" onClick={() => copy(content)}>복사</button></div></article>)}</>}
            </>}</div>
          </div>}
        </>}
      </div></section>
    </main><footer><div className="container"><strong>Marketing Manager.</strong><p>아이디어에서 초안까지. 브랜드의 다음 한 걸음.</p><p>실제 게시와 채널 연결은 다음 단계에서 제공됩니다.</p></div></footer>
    <dialog ref={editor} className="content-dialog" aria-labelledby="content-editor-title" onCancel={event => { event.preventDefault(); closeEditor(); }}><form onSubmit={save}><div className="dialog-heading"><div><p className="eyebrow">CONTENT EDITOR</p><h2 id="content-editor-title">초안 다듬기</h2></div><button type="button" className="close-button" aria-label="닫기" disabled={!!busy} onClick={closeEditor}>×</button></div><fieldset disabled={!!busy}><label>제목<input required maxLength={200} value={text.title} onChange={e => setText({ ...text, title: e.target.value })}/></label><label>본문<textarea required rows={14} maxLength={editing?.channel === "instagram" ? 2200 : editing?.channel === "linkedin" ? 3000 : 12000} value={text.body} onChange={e => setText({ ...text, body: e.target.value })}/></label></fieldset><p className="caption muted">{text.body.length.toLocaleString()}자 · 현재 v{editing?.revision}</p>{error && <p className="message" role="alert">{error}</p>}<div className="dialog-actions"><button type="button" className="text-button" disabled={!!busy} onClick={revisions}>수정 이력 보기</button><button type="button" className="button secondary" disabled={!!busy} onClick={closeEditor}>닫기</button><button className="button primary" disabled={!!busy || !dirty}>{busy === "save" ? "저장 중…" : "수정본 저장"}</button></div></form>{history.length>0 && <section className="revision-list"><h3>수정 이력</h3>{history.map(r => <details key={r.revision}><summary>v{r.revision} · {r.source === "ai" ? "AI 초안" : "직접 수정"}</summary><h4>{r.title}</h4><p>{r.body}</p></details>)}</section>}</dialog>
  </>;
}
