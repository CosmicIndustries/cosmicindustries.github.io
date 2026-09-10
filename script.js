const OWNER = 'CosmicIndustries';
const API = `https://api.github.com/users/${OWNER}/repos?per_page=100&sort=updated`;
const state = { repos: [], query: '', sort: 'updated' };

const $ = (id) => document.getElementById(id);

function escapeHTML(value = '') {
  return String(value).replace(/[&<>'"]/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
}

function formatDate(value) {
  if (!value) return '—';
  return new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short', day: 'numeric' }).format(new Date(value));
}

function repoCard(repo) {
  const language = repo.language ? `<span class="repo-lang">${escapeHTML(repo.language)}</span>` : '<span>mixed</span>';
  return `<article class="repo-card">
    <div class="project-meta"><span>${repo.fork ? 'FORK' : 'PROJECT'}</span><span>★ ${repo.stargazers_count}</span></div>
    <h3>${escapeHTML(repo.name)}</h3>
    <p>${escapeHTML(repo.description || 'Experimental project, research, tooling, or systems work.')}</p>
    <footer><span>${language} · ${formatDate(repo.updated_at)}</span><a href="${repo.html_url}" target="_blank" rel="noreferrer">Open ↗</a></footer>
  </article>`;
}

function renderRepos() {
  const query = state.query.trim().toLowerCase();
  let repos = state.repos.filter((repo) => {
    if (repo.archived) return false;
    const haystack = `${repo.name} ${repo.description || ''} ${repo.language || ''}`.toLowerCase();
    return haystack.includes(query);
  });

  repos.sort((a, b) => {
    if (state.sort === 'name') return a.name.localeCompare(b.name);
    if (state.sort === 'stars') return b.stargazers_count - a.stargazers_count;
    return new Date(b.updated_at) - new Date(a.updated_at);
  });

  $('repo-grid').innerHTML = repos.map(repoCard).join('') || '<div class="repo-status">No matching public projects.</div>';
  $('repo-status').textContent = `${repos.length} public project${repos.length === 1 ? '' : 's'} indexed · live from GitHub`;
}

async function loadRepos() {
  try {
    const response = await fetch(API, { headers: { Accept: 'application/vnd.github+json' } });
    if (!response.ok) throw new Error(`GitHub returned ${response.status}`);
    state.repos = await response.json();
    renderRepos();
  } catch (error) {
    $('repo-status').innerHTML = `Repository index unavailable. <a href="https://github.com/${OWNER}?tab=repositories" target="_blank" rel="noreferrer">Open GitHub directly ↗</a>`;
    console.error(error);
  }
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('cosmic-theme', theme);
  $('theme-toggle').textContent = theme === 'light' ? '☾' : '◐';
}

$('repo-search').addEventListener('input', (event) => { state.query = event.target.value; renderRepos(); });
$('repo-sort').addEventListener('change', (event) => { state.sort = event.target.value; renderRepos(); });
$('theme-toggle').addEventListener('click', () => applyTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light'));

$('year').textContent = new Date().getFullYear();
applyTheme(localStorage.getItem('cosmic-theme') || 'dark');
loadRepos();
