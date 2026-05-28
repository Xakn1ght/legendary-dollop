    (function(){
      const tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
      try { tg && tg.ready && tg.ready(); } catch(_) {}
      const backBtn = document.getElementById('backBtn');
      function goBack(){
        try{
          let url = '/webapp/dashboard/index.html';
          let propagate = true;
          try {
            const k = '__tma_ss_test__';
            sessionStorage.setItem(k, '1');
            sessionStorage.removeItem(k);
            propagate = false;
          } catch (_) {}
          let authToken = '';
          try { authToken = sessionStorage.getItem('tma_url_auth') || ''; } catch (_) {}
          if (!authToken) {
            try {
              const urlParams = new URLSearchParams(window.location.search);
              authToken = urlParams.get('auth') || '';
            } catch (_) {}
          }
          if (authToken && propagate) url += '?auth=' + encodeURIComponent(authToken);
          window.location.href = url;
        }catch(_){
          window.location.href = '/webapp/dashboard/index.html';
        }
      }
      if (backBtn) backBtn.addEventListener('click', goBack);
      try{
        if (tg && tg.BackButton) {
          // Keep Telegram's standard close button (don't replace it with BackButton UI)
          tg.BackButton.hide();
        }
      }catch(_){}
    })();
