window.__MOVIE_APP_EXTERNAL__ = true;

(() => {
  const API_BASE = 'http://127.0.0.1:5000/api';
  const ACTIVE_USER_STORAGE_KEY = 'movie-app-active-user-id';
  const HTML_ESCAPE = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  };

  const appLayout = document.querySelector('.app-layout');
  const userSelectPanel = document.getElementById('user-select-panel');
  const userGrid = userSelectPanel.querySelector('.user-grid');
  const moviesPanel = document.getElementById('movies-panel');
  const moviesList = moviesPanel.querySelector('.movie-grid');
  const actionPanel = document.getElementById('action-panel');
  const actionGrid = actionPanel.querySelector('.action-grid');
  const actionGridTemplate = actionGrid.innerHTML;
  const statsPanel = document.getElementById('stats-panel');
  const statsList = document.getElementById('stats-list');
  const randomPanel = document.getElementById('random-panel');
  const randomResult = document.getElementById('random-result');
  const commandPanel = document.getElementById('cli-action-input-panel');
  const commandView = document.getElementById('cli-command-view');
  const movieAddView = document.getElementById('movie-add-view');
  const movieDeleteView = document.getElementById('movie-delete-view');
  const movieUpdateView = document.getElementById('movie-update-view');
  const movieSearchView = document.getElementById('movie-search-view');
  const movieFilterView = document.getElementById('movie-filter-view');
  const commandInput = document.getElementById('cli-command-input');
  const commandSubmit = document.getElementById('cli-command-submit');
  const movieNameInput = document.getElementById('movie-name-input');
  const movieAddSubmit = document.getElementById('movie-add-submit');
  const movieAddStatus = document.getElementById('movie-add-status');
  const movieDeleteNameInput = document.getElementById('movie-delete-name-input');
  const movieDeleteSubmit = document.getElementById('movie-delete-submit');
  const movieDeleteStatus = document.getElementById('movie-delete-status');
  const movieUpdateNameInput = document.getElementById('movie-update-name-input');
  const movieUpdateNoteInput = document.getElementById('movie-update-note-input');
  const movieUpdateSubmit = document.getElementById('movie-update-submit');
  const movieUpdateStatus = document.getElementById('movie-update-status');
  const movieSearchInput = document.getElementById('movie-search-input');
  const movieSearchSubmit = document.getElementById('movie-search-submit');
  const movieSearchStatus = document.getElementById('movie-search-status');
  const movieSearchResults = document.getElementById('movie-search-results');
  const movieFilterMinRatingInput = document.getElementById('movie-filter-min-rating-input');
  const movieFilterStartYearInput = document.getElementById('movie-filter-start-year-input');
  const movieFilterEndYearInput = document.getElementById('movie-filter-end-year-input');
  const movieFilterSubmit = document.getElementById('movie-filter-submit');
  const movieFilterStatus = document.getElementById('movie-filter-status');
  const movieFilterResults = document.getElementById('movie-filter-results');
  const selectedUserName = document.getElementById('selected-user');
  const userSelectPrompt = document.querySelector('.user-select-panel p');
  const cliItems = document.querySelectorAll('[data-cli-choice]');
  let actionCards = [];

  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => HTML_ESCAPE[character]);

  const apiFetch = async (path, options = {}) => {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
      ...options,
    });

    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json')
      ? await response.json().catch(() => ({}))
      : await response.text();

    if (!response.ok) {
      const message = typeof payload === 'string'
        ? payload
        : payload?.error || response.statusText || 'Request failed.';
      throw new Error(message);
    }

    return payload;
  };

  const refreshActionCards = () => {
    actionCards = Array.from(actionGrid.querySelectorAll('.action-card'));
  };

  const restoreActionGrid = () => {
    actionGrid.innerHTML = actionGridTemplate;
    actionGrid.classList.remove('action-grid--detail');
    refreshActionCards();
  };

  const setDetailActionGrid = () => {
    actionGrid.classList.add('action-grid--detail');
  };

  const hideActionCards = () => {
    actionCards.forEach((actionCard) => {
      actionCard.classList.remove('action-card--active', 'selected', 'is-visible');
      actionCard.classList.add('is-hidden');
    });
  };

  const showCommandPanel = () => {
    appLayout.classList.remove('app-layout--no-command-panel');
    commandPanel.hidden = false;
    commandPanel.style.display = '';
    commandPanel.classList.remove('is-hidden');
  };

  const hideCommandPanel = () => {
    appLayout.classList.add('app-layout--no-command-panel');
    commandPanel.hidden = true;
    commandPanel.style.display = 'none';
    commandPanel.classList.add('is-hidden');
  };

  const hideStatsView = () => {
    statsPanel.classList.add('is-hidden');
  };

  const hideRandomView = () => {
    randomPanel.classList.add('is-hidden');
  };

  const hideSearchView = () => {
    movieSearchView.classList.add('is-hidden');
    movieSearchStatus.textContent = '';
    movieSearchResults.replaceChildren();
  };

  const hideFilterView = () => {
    movieFilterView.classList.add('is-hidden');
    movieFilterStatus.textContent = '';
    movieFilterResults.replaceChildren();
  };

  const showCliMenu = () => {
    appLayout.classList.remove('app-layout--menu-hidden');
  };

  const renderMovieGrid = (container, movies, className = 'movie-grid') => {
    container.className = className;
    container.innerHTML = movies.map(movieMarkup).join('');
  };

  const movieMarkup = (movie) => {
    const title = escapeHtml(movie.title || 'Unknown');
    const year = escapeHtml(movie.year || 'Unknown');
    const note = movie.note ? String(movie.note) : '';
    const safeNote = escapeHtml(note);
    const safeNoteAttr = escapeHtml(note);
    const poster = movie.poster && movie.poster !== 'N/A'
      ? `<img class="movie-poster" src="${escapeHtml(movie.poster)}" alt="${title} poster" data-note="${safeNoteAttr}"/>`
      : `<div class="movie-poster" data-note="${safeNoteAttr}"></div>`;
    const imdbLink = movie.imdb_id
      ? `https://www.imdb.com/title/${encodeURIComponent(movie.imdb_id)}/`
      : `https://www.imdb.com/find/?q=${encodeURIComponent(movie.title || '')}&ref_=nv_sr_fn`;
    const starsValue = Number.parseFloat(movie.rating);
    const normalized = Number.isFinite(starsValue) ? Math.max(0, Math.min(10, starsValue)) : 0;
    const filledStars = Math.round(normalized / 2);
    const stars = Array.from({ length: 5 }, (_, index) => (
      `<span class="star${index < filledStars ? ' filled' : ' empty'}">${index < filledStars ? '&#9733;' : '&#9734;'}</span>`
    )).join('');
    const rating = normalized.toFixed(1);
    const noteMarkup = note ? `<span class="movie-note">${safeNote}</span>` : '';

    return `
      <li>
        <div class="movie">
          <div class="movie-rating-stars" aria-label="Rating ${rating} out of 10">
            ${stars}
            <span class="rating-value">${rating}</span>
          </div>
          <div class="movie-poster-wrap">
            <a class="movie-poster-link" href="${escapeHtml(imdbLink)}" target="_blank" rel="noopener noreferrer">
              ${poster}
            </a>
            ${noteMarkup}
          </div>
          <div class="movie-title">${title}</div>
          <div class="movie-year">${year}</div>
        </div>
      </li>
    `;
  };

  const renderSelectedUser = (user) => {
    selectedUserName.textContent = user.display_name;
    userSelectPrompt.textContent = `Selected: ${user.display_name}`;
  };

  const renderUserGrid = (users, activeUserId) => {
    const sortedUsers = [...users].sort((left, right) => left.display_name.localeCompare(right.display_name));
    const userButtons = sortedUsers.map((user) => (
      `<button type="button" class="user-card${Number(user.id) === Number(activeUserId) ? ' selected' : ''}" data-user-id="${user.id}" data-user-name="${escapeHtml(user.display_name)}">${escapeHtml(user.display_name)}</button>`
    )).join('');
    userGrid.innerHTML = `${userButtons}<button type="button" class="user-card user-card-new" data-action="create-user">Create new user</button>`;
  };

  const getUsers = async () => {
    const payload = await apiFetch('/users');
    return payload.users || [];
  };

  const getActiveUser = async () => {
    const payload = await apiFetch('/users/active');
    return payload;
  };

  const setActiveUser = async (userId) => {
    const payload = await apiFetch('/users/active', {
      method: 'POST',
      body: JSON.stringify({ id: userId }),
    });
    localStorage.setItem(ACTIVE_USER_STORAGE_KEY, String(payload.id));
    const users = await getUsers();
    renderUserGrid(users, payload.id);
    const user = users.find((entry) => Number(entry.id) === Number(payload.id)) || payload;
    renderSelectedUser(user);
    return payload;
  };

  const showStartPage = () => {
    appLayout.classList.add('app-layout--menu-hidden');
    appLayout.classList.remove('app-layout--no-command-panel');
    userSelectPanel.classList.remove('is-hidden');
    moviesPanel.classList.add('is-hidden');
    actionPanel.classList.add('is-hidden');
    commandPanel.hidden = true;
    commandPanel.style.display = 'none';
    commandPanel.classList.add('is-hidden');
    hideStatsView();
    hideRandomView();
    hideSearchView();
    hideFilterView();
    restoreActionGrid();
    hideActionCards();
    commandInput.value = '';
    movieNameInput.value = '';
    movieDeleteNameInput.value = '';
    movieUpdateNameInput.value = '';
    movieUpdateNoteInput.value = '';
    movieSearchInput.value = '';
    movieFilterMinRatingInput.value = '';
    movieFilterStartYearInput.value = '';
    movieFilterEndYearInput.value = '';
  };

  const loadMovies = async () => {
    const payload = await apiFetch('/movies');
    const movies = payload.movies || [];
    renderMovieGrid(moviesList, movies);
    return movies;
  };

  const showMovieList = async () => {
    await loadMovies();
    restoreActionGrid();
    showCliMenu();
    userSelectPanel.classList.add('is-hidden');
    moviesPanel.classList.remove('is-hidden');
    actionPanel.classList.add('is-hidden');
    hideStatsView();
    hideRandomView();
    hideSearchView();
    hideFilterView();
    commandPanel.classList.add('is-hidden');
    hideActionCards();
  };

  const showStatsView = async () => {
    const payload = await apiFetch('/movies/stats');
    const stats = payload.stats || {};

    statsList.replaceChildren();

    if (!stats.count) {
      const emptyItem = document.createElement('li');
      emptyItem.innerHTML = '<span class="stats-label">No movies</span><span class="stats-value">No statistics available</span>';
      statsList.appendChild(emptyItem);
    } else {
      const rows = [
        ['Movie count', String(stats.count)],
        ['Average rating', Number(stats.average_rating || 0).toFixed(1)],
        ['Median rating', Number(stats.median_rating || 0).toFixed(1)],
        ['Best movie', stats.best_movie ? `${stats.best_movie.title} (${Number(stats.best_movie.rating || 0).toFixed(1)})` : 'n/a'],
        ['Worst movie', stats.worst_movie ? `${stats.worst_movie.title} (${Number(stats.worst_movie.rating || 0).toFixed(1)})` : 'n/a'],
      ];

      rows.forEach(([label, value]) => {
        const item = document.createElement('li');
        const labelSpan = document.createElement('span');
        labelSpan.className = 'stats-label';
        labelSpan.textContent = label;
        const valueSpan = document.createElement('span');
        valueSpan.className = 'stats-value';
        valueSpan.textContent = value;
        item.append(labelSpan, valueSpan);
        statsList.appendChild(item);
      });
    }

    moviesPanel.classList.add('is-hidden');
    actionPanel.classList.add('is-hidden');
    commandPanel.classList.add('is-hidden');
    hideSearchView();
    hideRandomView();
    statsPanel.classList.remove('is-hidden');
    hideActionCards();
  };

  const showRandomMovieView = async () => {
    const payload = await apiFetch('/movies/random');
    const movie = payload.movie;

    randomResult.replaceChildren();

    if (!movie) {
      const emptyState = document.createElement('p');
      emptyState.className = 'random-empty';
      emptyState.textContent = 'No movies available.';
      randomResult.appendChild(emptyState);
    } else {
      const card = document.createElement('div');
      card.className = 'random-card';

      if (movie.poster && movie.poster !== 'N/A') {
        const img = document.createElement('img');
        img.className = 'random-poster';
        img.src = movie.poster;
        img.alt = `${movie.title} poster`;
        card.appendChild(img);
      }

      const title = document.createElement('h3');
      title.className = 'random-title';
      title.textContent = movie.title;

      const meta = document.createElement('p');
      meta.className = 'random-meta';
      meta.textContent = `${movie.year} | Rating ${Number(movie.rating || 0).toFixed(1)}`;

      const note = document.createElement('p');
      note.className = 'random-note';
      note.textContent = `Your movie for tonight: ${movie.title}.`;

      card.append(title, meta, note);
      randomResult.appendChild(card);
    }

    moviesPanel.classList.add('is-hidden');
    actionPanel.classList.add('is-hidden');
    commandPanel.classList.add('is-hidden');
    hideSearchView();
    hideStatsView();
    randomPanel.classList.remove('is-hidden');
    hideActionCards();
  };

  const showSearchView = () => {
    showCommandPanel();
    commandView.classList.add('is-hidden');
    movieAddView.classList.add('is-hidden');
    movieDeleteView.classList.add('is-hidden');
    movieUpdateView.classList.add('is-hidden');
    movieSearchView.classList.remove('is-hidden');
    hideFilterView();
    hideStatsView();
    hideRandomView();
    movieAddStatus.textContent = '';
    movieDeleteStatus.textContent = '';
    movieUpdateStatus.textContent = '';
    movieSearchStatus.textContent = '';
    window.setTimeout(() => movieSearchInput.focus(), 0);
  };

  const showFilterView = () => {
    showCommandPanel();
    commandView.classList.add('is-hidden');
    movieAddView.classList.add('is-hidden');
    movieDeleteView.classList.add('is-hidden');
    movieUpdateView.classList.add('is-hidden');
    movieSearchView.classList.add('is-hidden');
    movieFilterView.classList.remove('is-hidden');
    hideStatsView();
    hideRandomView();
    movieAddStatus.textContent = '';
    movieDeleteStatus.textContent = '';
    movieUpdateStatus.textContent = '';
    movieSearchStatus.textContent = '';
    movieFilterStatus.textContent = '';
    movieFilterResults.replaceChildren();
    window.setTimeout(() => movieFilterMinRatingInput.focus(), 0);
  };

  const showCommandView = () => {
    showCommandPanel();
    commandView.classList.remove('is-hidden');
    movieAddView.classList.add('is-hidden');
    movieDeleteView.classList.add('is-hidden');
    movieUpdateView.classList.add('is-hidden');
    movieSearchView.classList.add('is-hidden');
    movieFilterView.classList.add('is-hidden');
    hideStatsView();
    hideRandomView();
    movieAddStatus.textContent = '';
    movieDeleteStatus.textContent = '';
    movieUpdateStatus.textContent = '';
  };

  const showAddMovieView = () => {
    showCommandPanel();
    commandView.classList.add('is-hidden');
    movieAddView.classList.remove('is-hidden');
    movieDeleteView.classList.add('is-hidden');
    movieUpdateView.classList.add('is-hidden');
    hideSearchView();
    hideFilterView();
    hideStatsView();
    hideRandomView();
    movieAddStatus.textContent = '';
    movieDeleteStatus.textContent = '';
    movieUpdateStatus.textContent = '';
    window.setTimeout(() => movieNameInput.focus(), 0);
  };

  const showDeleteMovieView = () => {
    showCommandPanel();
    commandView.classList.add('is-hidden');
    movieAddView.classList.add('is-hidden');
    movieDeleteView.classList.remove('is-hidden');
    movieUpdateView.classList.add('is-hidden');
    hideSearchView();
    hideStatsView();
    hideRandomView();
    movieAddStatus.textContent = '';
    movieDeleteStatus.textContent = '';
    movieUpdateStatus.textContent = '';
    window.setTimeout(() => movieDeleteNameInput.focus(), 0);
  };

  const showUpdateMovieView = () => {
    showCommandPanel();
    commandView.classList.add('is-hidden');
    movieAddView.classList.add('is-hidden');
    movieDeleteView.classList.add('is-hidden');
    movieUpdateView.classList.remove('is-hidden');
    hideSearchView();
    hideFilterView();
    hideStatsView();
    hideRandomView();
    movieAddStatus.textContent = '';
    movieDeleteStatus.textContent = '';
    movieUpdateStatus.textContent = '';
    window.setTimeout(() => movieUpdateNameInput.focus(), 0);
  };

  const renderSearchResults = async (term) => {
    const query = String(term ?? '').trim();
    movieSearchResults.replaceChildren();

    const header = document.createElement('p');
    header.className = 'search-results-summary';

    if (!query) {
      header.textContent = 'Please enter a movie name.';
      movieSearchResults.appendChild(header);
      return false;
    }

    const payload = await apiFetch(`/movies/search?term=${encodeURIComponent(query)}`);
    const movies = payload.movies || [];

    header.textContent = movies.length
      ? `Found ${movies.length} match${movies.length === 1 ? '' : 'es'} for "${query}".`
      : `No movies found for "${query}".`;
    movieSearchResults.appendChild(header);

    if (movies.length) {
      const resultsList = document.createElement('ol');
      resultsList.className = 'movie-grid movie-grid--search-results';
      resultsList.innerHTML = movies.map(movieMarkup).join('');
      movieSearchResults.appendChild(resultsList);
    }

    return true;
  };

  const renderFilterResults = async () => {
    const minRatingText = movieFilterMinRatingInput.value.trim();
    const startYearText = movieFilterStartYearInput.value.trim();
    const endYearText = movieFilterEndYearInput.value.trim();

    if ((minRatingText && Number.isNaN(Number.parseFloat(minRatingText)))
      || (startYearText && Number.isNaN(Number.parseInt(startYearText, 10)))
      || (endYearText && Number.isNaN(Number.parseInt(endYearText, 10)))) {
      const header = document.createElement('p');
      header.className = 'search-results-summary';
      header.textContent = 'Please enter valid filter values.';
      movieFilterResults.replaceChildren(header);
      return false;
    }

    const query = new URLSearchParams();
    if (minRatingText) query.set('min_rating', minRatingText);
    if (startYearText) query.set('start_year', startYearText);
    if (endYearText) query.set('end_year', endYearText);

    const payload = await apiFetch(`/movies/filter?${query.toString()}`);
    const movies = payload.movies || [];
    movieFilterResults.replaceChildren();

    const header = document.createElement('p');
    header.className = 'search-results-summary';
    const filterSummaryParts = [];
    if (minRatingText) filterSummaryParts.push(`rating >= ${minRatingText}`);
    if (startYearText) filterSummaryParts.push(`year >= ${startYearText}`);
    if (endYearText) filterSummaryParts.push(`year <= ${endYearText}`);

    header.textContent = movies.length
      ? `Found ${movies.length} movie${movies.length === 1 ? '' : 's'}${filterSummaryParts.length ? ` for ${filterSummaryParts.join(', ')}` : ''}.`
      : 'No movies found matching the criteria.';
    movieFilterResults.appendChild(header);

    if (movies.length) {
      const resultsList = document.createElement('ol');
      resultsList.className = 'movie-grid movie-grid--search-results';
      resultsList.innerHTML = movies.map(movieMarkup).join('');
      movieFilterResults.appendChild(resultsList);
    }

    return true;
  };

  const renderSortedMovieResults = async (headline, sortBy) => {
    const payload = await apiFetch(`/movies/sorted?by=${encodeURIComponent(sortBy)}`);
    const movies = payload.movies || [];

    restoreActionGrid();
    setDetailActionGrid();
    actionGrid.replaceChildren();

    const summary = document.createElement('p');
    summary.className = 'search-results-summary';
    summary.textContent = movies.length ? headline : 'No movies available.';
    actionGrid.appendChild(summary);

    if (movies.length) {
      const resultsList = document.createElement('ol');
      resultsList.className = 'movie-grid movie-grid--search-results';
      resultsList.innerHTML = movies.map(movieMarkup).join('');
      actionGrid.appendChild(resultsList);
    }
  };

  const renderRatingHistogram = async () => {
    const payload = await apiFetch('/movies/histogram');
    const movies = payload.movies || [];

    restoreActionGrid();
    setDetailActionGrid();
    actionGrid.replaceChildren();

    const summary = document.createElement('p');
    summary.className = 'search-results-summary';
    summary.textContent = movies.length ? 'Movie ratings histogram (sorted by rating).' : 'No movies available.';
    actionGrid.appendChild(summary);

    if (!movies.length) {
      return;
    }

    const chartWrap = document.createElement('div');
    chartWrap.className = 'rating-histogram-wrap';

    const svgNS = 'http://www.w3.org/2000/svg';
    const width = 960;
    const height = 360;
    const margin = { top: 28, right: 20, bottom: 92, left: 48 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const barGap = 8;
    const barWidth = Math.max(14, Math.floor((plotWidth - barGap * (movies.length - 1)) / movies.length));
    const baselineY = margin.top + plotHeight;

    const svg = document.createElementNS(svgNS, 'svg');
    svg.setAttribute('class', 'rating-histogram-svg');
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'Movie ratings bar chart');

    const background = document.createElementNS(svgNS, 'rect');
    background.setAttribute('x', '0');
    background.setAttribute('y', '0');
    background.setAttribute('width', String(width));
    background.setAttribute('height', String(height));
    background.setAttribute('rx', '18');
    background.setAttribute('fill', '#f6fbf7');
    svg.appendChild(background);

    const title = document.createElementNS(svgNS, 'text');
    title.setAttribute('x', String(margin.left));
    title.setAttribute('y', '20');
    title.setAttribute('class', 'rating-histogram-title');
    title.textContent = 'Ratings by movie';
    svg.appendChild(title);

    const axisLine = document.createElementNS(svgNS, 'line');
    axisLine.setAttribute('x1', String(margin.left));
    axisLine.setAttribute('y1', String(baselineY));
    axisLine.setAttribute('x2', String(width - margin.right));
    axisLine.setAttribute('y2', String(baselineY));
    axisLine.setAttribute('class', 'rating-histogram-axis');
    svg.appendChild(axisLine);

    const maxRating = 10;

    movies.forEach((movie, index) => {
      const rating = Number.parseFloat(movie.rating || 0) || 0;
      const barHeight = Math.max(2, Math.round((rating / maxRating) * plotHeight));
      const x = margin.left + index * (barWidth + barGap);
      const y = baselineY - barHeight;
      const label = movie.title.length > 18 ? `${movie.title.slice(0, 17)}…` : movie.title;

      const bar = document.createElementNS(svgNS, 'rect');
      bar.setAttribute('x', String(x));
      bar.setAttribute('y', String(y));
      bar.setAttribute('width', String(barWidth));
      bar.setAttribute('height', String(barHeight));
      bar.setAttribute('rx', '6');
      bar.setAttribute('class', 'rating-histogram-bar');
      svg.appendChild(bar);

      const value = document.createElementNS(svgNS, 'text');
      value.setAttribute('x', String(x + barWidth / 2));
      value.setAttribute('y', String(y - 8));
      value.setAttribute('text-anchor', 'middle');
      value.setAttribute('class', 'rating-histogram-value');
      value.textContent = rating.toFixed(1);
      svg.appendChild(value);

      const labelText = document.createElementNS(svgNS, 'text');
      labelText.setAttribute('x', String(x + barWidth / 2));
      labelText.setAttribute('y', String(baselineY + 22));
      labelText.setAttribute('text-anchor', 'end');
      labelText.setAttribute('transform', `rotate(-45 ${x + barWidth / 2} ${baselineY + 22})`);
      labelText.setAttribute('class', 'rating-histogram-label');
      labelText.textContent = label;
      svg.appendChild(labelText);
    });

    chartWrap.appendChild(svg);
    actionGrid.appendChild(chartWrap);
  };

  const runCliChoice = async (choice) => {
    const chosenChoice = String(choice ?? '').trim();
    restoreActionGrid();

    if (!chosenChoice) {
      commandInput.focus();
      return;
    }

    if (chosenChoice === '1') {
      await showMovieList();
      return;
    }

    if (chosenChoice === '2') {
      moviesPanel.classList.add('is-hidden');
      actionPanel.classList.add('is-hidden');
      hideActionCards();
      showAddMovieView();
      return;
    }

    if (chosenChoice === '3') {
      moviesPanel.classList.add('is-hidden');
      actionPanel.classList.add('is-hidden');
      hideActionCards();
      showDeleteMovieView();
      return;
    }

    if (chosenChoice === '4') {
      moviesPanel.classList.add('is-hidden');
      actionPanel.classList.add('is-hidden');
      hideActionCards();
      showUpdateMovieView();
      return;
    }

    if (chosenChoice === '5') {
      await showStatsView();
      return;
    }

    if (chosenChoice === '6') {
      await showRandomMovieView();
      return;
    }

    if (chosenChoice === '7') {
      moviesPanel.classList.add('is-hidden');
      actionPanel.classList.add('is-hidden');
      hideActionCards();
      showSearchView();
      return;
    }

    if (chosenChoice === '8') {
      moviesPanel.classList.add('is-hidden');
      actionPanel.classList.remove('is-hidden');
      commandPanel.classList.add('is-hidden');
      hideStatsView();
      hideRandomView();
      hideSearchView();
      hideFilterView();
      await renderSortedMovieResults('Movies sorted by rating (highest first).', 'rating');
      return;
    }

    if (chosenChoice === '9') {
      moviesPanel.classList.add('is-hidden');
      actionPanel.classList.remove('is-hidden');
      commandPanel.classList.add('is-hidden');
      hideStatsView();
      hideRandomView();
      hideSearchView();
      hideFilterView();
      await renderSortedMovieResults('Movies sorted by year (newest first).', 'year');
      return;
    }

    if (chosenChoice === '10') {
      moviesPanel.classList.add('is-hidden');
      actionPanel.classList.remove('is-hidden');
      commandPanel.classList.add('is-hidden');
      hideStatsView();
      hideRandomView();
      hideSearchView();
      hideFilterView();
      await renderRatingHistogram();
      return;
    }

    if (chosenChoice === '11') {
      moviesPanel.classList.add('is-hidden');
      actionPanel.classList.add('is-hidden');
      hideActionCards();
      showFilterView();
      return;
    }

    if (chosenChoice === '12') {
      showStartPage();
      return;
    }

    actionCards.forEach((actionCard) => {
      const isSelected = actionCard.dataset.actionChoice === chosenChoice;
      actionCard.classList.toggle('is-hidden', !isSelected);
      actionCard.classList.toggle('is-visible', isSelected);
      actionCard.classList.toggle('action-card--active', isSelected);
      actionCard.classList.toggle('selected', isSelected);
    });

    moviesPanel.classList.add('is-hidden');
    actionPanel.classList.remove('is-hidden');
    showCommandView();
  };

  const createUserFromPrompt = async () => {
    const firstNameInput = window.prompt('Enter new user first name:');
    if (firstNameInput === null) {
      return;
    }

    const firstName = firstNameInput.trim();
    if (!firstName) {
      window.alert('User name cannot be empty.');
      return;
    }

    const lastNameInput = window.prompt('Enter new user last name (optional):');
    if (lastNameInput === null) {
      return;
    }

    const lastName = lastNameInput.trim();
    const payload = await apiFetch('/users', {
      method: 'POST',
      body: JSON.stringify({ name: firstName, last_name: lastName }),
    });

    renderSelectedUser(payload);
    localStorage.setItem(ACTIVE_USER_STORAGE_KEY, String(payload.id));
    renderUserGrid(await getUsers(), payload.id);
    await showMovieList();
  };

  userGrid.addEventListener('click', async (event) => {
    const button = event.target.closest('button');
    if (!button) {
      return;
    }

    if (button.dataset.action === 'create-user') {
      await createUserFromPrompt();
      return;
    }

    const userId = Number.parseInt(button.dataset.userId, 10);
    if (!Number.isFinite(userId)) {
      return;
    }

    const userName = button.dataset.userName || button.textContent.trim();
    await setActiveUser(userId);
    renderSelectedUser({ display_name: userName });
    showCliMenu();
    userSelectPanel.classList.add('is-hidden');
    moviesPanel.classList.remove('is-hidden');
    actionPanel.classList.add('is-hidden');
    commandPanel.classList.add('is-hidden');
    hideStatsView();
    hideRandomView();
    hideSearchView();
    hideFilterView();
    hideActionCards();
    await showMovieList();
  });

  cliItems.forEach((cliItem) => {
    cliItem.addEventListener('click', async () => {
      const choice = cliItem.dataset.cliChoice;
      commandInput.value = choice;
      await runCliChoice(choice);
    });
  });

  commandSubmit.addEventListener('click', async () => {
    await runCliChoice(commandInput.value);
  });

  commandInput.addEventListener('keyup', async (event) => {
    if (event.key === 'Enter') {
      await runCliChoice(commandInput.value);
    }
  });

  movieAddSubmit.addEventListener('click', async () => {
    const movieName = movieNameInput.value.trim();
    if (!movieName) {
      movieAddStatus.textContent = 'Please enter a movie name.';
      movieNameInput.focus();
      return;
    }

    movieAddStatus.textContent = 'Adding movie...';
    try {
      await apiFetch('/movies/add', {
        method: 'POST',
        body: JSON.stringify({ title: movieName }),
      });
      movieAddStatus.textContent = `Added "${movieName}".`;
      movieNameInput.value = '';
      await showMovieList();
    } catch (error) {
      movieAddStatus.textContent = error.message;
    }
  });

  movieNameInput.addEventListener('keyup', (event) => {
    if (event.key === 'Enter') {
      movieAddSubmit.click();
    }
  });

  movieDeleteSubmit.addEventListener('click', async () => {
    const movieName = movieDeleteNameInput.value.trim();
    if (!movieName) {
      movieDeleteStatus.textContent = 'Please enter a movie name.';
      movieDeleteNameInput.focus();
      return;
    }

    movieDeleteStatus.textContent = 'Deleting movie...';
    try {
      await apiFetch('/movies/delete', {
        method: 'POST',
        body: JSON.stringify({ title: movieName }),
      });
      movieDeleteStatus.textContent = `Deleted "${movieName}".`;
      movieDeleteNameInput.value = '';
      await showMovieList();
    } catch (error) {
      movieDeleteStatus.textContent = error.message;
    }
  });

  movieDeleteNameInput.addEventListener('keyup', (event) => {
    if (event.key === 'Enter') {
      movieDeleteSubmit.click();
    }
  });

  movieUpdateSubmit.addEventListener('click', async () => {
    const movieName = movieUpdateNameInput.value.trim();
    const movieNote = movieUpdateNoteInput.value.trim();

    if (!movieName) {
      movieUpdateStatus.textContent = 'Please enter a movie name.';
      movieUpdateNameInput.focus();
      return;
    }

    movieUpdateStatus.textContent = 'Updating movie...';
    try {
      await apiFetch('/movies/update', {
        method: 'POST',
        body: JSON.stringify({ title: movieName, note: movieNote }),
      });
      movieUpdateStatus.textContent = `Updated "${movieName}".`;
      await showMovieList();
    } catch (error) {
      movieUpdateStatus.textContent = error.message;
    }
  });

  movieUpdateNameInput.addEventListener('keyup', (event) => {
    if (event.key === 'Enter') {
      movieUpdateNoteInput.focus();
    }
  });

  movieUpdateNoteInput.addEventListener('keyup', (event) => {
    if (event.key === 'Enter' && event.ctrlKey) {
      movieUpdateSubmit.click();
    }
  });

  movieSearchSubmit.addEventListener('click', async () => {
    const searchTerm = movieSearchInput.value.trim();
    if (!searchTerm) {
      movieSearchStatus.textContent = 'Please enter a search term.';
      movieSearchInput.focus();
      return;
    }

    try {
      const hasResults = await renderSearchResults(searchTerm);
      movieSearchStatus.textContent = hasResults
        ? `Showing results for "${searchTerm}".`
        : `No movies found for "${searchTerm}".`;
      commandPanel.classList.remove('is-hidden');
      movieSearchView.classList.remove('is-hidden');
      actionPanel.classList.add('is-hidden');
      moviesPanel.classList.add('is-hidden');
    } catch (error) {
      movieSearchStatus.textContent = error.message;
    }
  });

  movieFilterSubmit.addEventListener('click', async () => {
    try {
      const hasResults = await renderFilterResults();
      if (!hasResults) {
        movieFilterStatus.textContent = 'Please enter valid filter values.';
        return;
      }

      movieFilterStatus.textContent = 'Filter applied.';
      commandPanel.classList.remove('is-hidden');
      movieFilterView.classList.remove('is-hidden');
      actionPanel.classList.add('is-hidden');
      moviesPanel.classList.add('is-hidden');
    } catch (error) {
      movieFilterStatus.textContent = error.message;
    }
  });

  movieSearchInput.addEventListener('keyup', (event) => {
    if (event.key === 'Enter') {
      movieSearchSubmit.click();
    }
  });

  [movieFilterMinRatingInput, movieFilterStartYearInput, movieFilterEndYearInput].forEach((input) => {
    input.addEventListener('keyup', (event) => {
      if (event.key === 'Enter') {
        movieFilterSubmit.click();
      }
    });
  });

  const bootstrap = async () => {
    const users = await getUsers();
    const activeUser = await getActiveUser();
    renderUserGrid(users, activeUser.id);
    localStorage.setItem(ACTIVE_USER_STORAGE_KEY, String(activeUser.id));
    refreshActionCards();
    showStartPage();
  };

  commandInput.setAttribute('aria-label', 'Command input');
  bootstrap().catch((error) => {
    console.error(error);
    userSelectPrompt.textContent = 'Could not load movie data.';
  });
})();
