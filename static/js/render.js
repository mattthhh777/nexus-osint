// ══════════════════════════════════════════════════════
//  RENDER — Results rendering and victim file viewer
// ══════════════════════════════════════════════════════
let breachPage = 0;
const BREACH_PAGE_SIZE = 25;
let pwdVisible = {};
let openVictimTrees = {};   // {log_id: treeData}
let openTreeDirs    = {};   // {node_id: bool}

// ── Social Icons — Simple Icons SVG paths (viewBox 0 0 24 24) ────────────────
// Hardcoded paths for the 25 Sherlock platforms. No external requests needed.
const _SI = {
  github:     'M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12',
  gitlab:     'M22.65 14.39L12 22.13 1.35 14.39a.84.84 0 0 1-.3-.94l1.22-3.78 2.44-7.51A.42.42 0 0 1 4.82 2a.43.43 0 0 1 .58 0 .42.42 0 0 1 .11.18l2.44 7.49h8.1l2.44-7.51A.42.42 0 0 1 18.6 2a.43.43 0 0 1 .58 0 .42.42 0 0 1 .11.18l2.44 7.51L23 13.45a.84.84 0 0 1-.35.94z',
  x:          'M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z',
  instagram:  'M12 0C8.74 0 8.333.015 7.053.072 5.775.132 4.905.333 4.14.63c-.789.306-1.459.717-2.126 1.384S.935 3.35.63 4.14C.333 4.905.131 5.775.072 7.053.012 8.333 0 8.74 0 12c0 3.259.014 3.668.072 4.948.058 1.278.261 2.148.558 2.913.306.788.717 1.459 1.384 2.126.667.666 1.336 1.079 2.126 1.384.766.296 1.636.499 2.913.558C8.333 23.988 8.74 24 12 24c3.259 0 3.668-.014 4.948-.072 1.278-.058 2.148-.261 2.913-.558.788-.306 1.459-.718 2.126-1.384.666-.667 1.079-1.335 1.384-2.126.296-.765.499-1.635.558-2.913.06-1.28.072-1.689.072-4.948 0-3.259-.014-3.667-.072-4.947-.058-1.278-.261-2.147-.558-2.913-.306-.789-.718-1.459-1.384-2.126C21.319 1.347 20.651.935 19.86.63c-.765-.297-1.636-.499-2.913-.558C15.667.012 15.26 0 12 0zm0 2.16c3.203 0 3.585.016 4.85.071 1.17.055 1.805.249 2.227.415.562.217.96.477 1.382.896.419.42.679.819.896 1.381.164.422.36 1.057.413 2.227.057 1.266.07 1.646.07 4.85s-.015 3.585-.074 4.85c-.061 1.17-.256 1.805-.421 2.227-.224.562-.479.96-.899 1.382-.419.419-.824.679-1.38.896-.42.164-1.065.36-2.235.413-1.274.057-1.649.07-4.859.07-3.211 0-3.586-.015-4.859-.074-1.171-.061-1.816-.256-2.236-.421-.569-.224-.96-.479-1.379-.899-.421-.419-.69-.824-.9-1.38-.165-.42-.359-1.065-.42-2.235-.045-1.26-.061-1.649-.061-4.844 0-3.196.016-3.586.061-4.861.061-1.17.255-1.814.42-2.234.21-.57.479-.96.9-1.381.419-.419.81-.689 1.379-.898.42-.166 1.051-.361 2.221-.421 1.275-.045 1.65-.06 4.859-.06zm0 3.678c-3.405 0-6.162 2.76-6.162 6.162 0 3.405 2.76 6.162 6.162 6.162 3.405 0 6.162-2.76 6.162-6.162 0-3.405-2.76-6.162-6.162-6.162zM12 16c-2.21 0-4-1.79-4-4s1.79-4 4-4 4 1.79 4 4-1.79 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z',
  tiktok:     'M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z',
  reddit:     'M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z',
  linkedin:   'M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z',
  youtube:    'M23.495 6.205a3.007 3.007 0 0 0-2.088-2.088c-1.87-.501-9.396-.501-9.396-.501s-7.507-.01-9.396.501A3.007 3.007 0 0 0 .527 6.205a31.247 31.247 0 0 0-.522 5.805 31.247 31.247 0 0 0 .522 5.783 3.007 3.007 0 0 0 2.088 2.088c1.868.502 9.396.502 9.396.502s7.506 0 9.396-.502a3.007 3.007 0 0 0 2.088-2.088 31.247 31.247 0 0 0 .5-5.783 31.247 31.247 0 0 0-.5-5.805zM9.609 15.601V8.408l6.264 3.602z',
  twitch:     'M11.571 4.714h1.715v5.143H11.57zm4.715 0H18v5.143h-1.714zM6 0L1.714 4.286v15.428h5.143V24l4.286-4.286h3.428L22.286 12V0zm14.571 11.143l-3.428 3.428h-3.429l-3 3v-3H6.857V1.714h13.714z',
  steam:      'M11.979 0C5.678 0 .511 4.86.022 11.037l6.432 2.658c.545-.371 1.203-.59 1.912-.59.063 0 .125.004.188.006l2.861-4.142V8.91c0-2.495 2.028-4.524 4.524-4.524 2.494 0 4.524 2.029 4.524 4.527s-2.03 4.525-4.524 4.525h-.105l-4.076 2.911c0 .052.004.105.004.159 0 1.875-1.515 3.396-3.39 3.396-1.635 0-3.016-1.173-3.331-2.727L.436 15.27C1.862 20.307 6.486 24 11.979 24c6.627 0 11.999-5.373 11.999-12S18.605 0 11.979 0zM7.54 18.21l-1.473-.61c.262.543.714.999 1.314 1.25 1.297.539 2.793-.076 3.332-1.375.263-.63.264-1.319.005-1.949s-.75-1.121-1.377-1.383c-.624-.26-1.29-.249-1.878-.03l1.523.63c.956.4 1.409 1.5 1.009 2.455-.397.957-1.497 1.41-2.455 1.012H7.54zm11.415-9.303c0-1.662-1.353-3.015-3.015-3.015-1.665 0-3.015 1.353-3.015 3.015 0 1.665 1.35 3.015 3.015 3.015 1.663 0 3.015-1.35 3.015-3.015zm-5.273-.005c0-1.252 1.013-2.266 2.265-2.266 1.249 0 2.266 1.014 2.266 2.266 0 1.251-1.017 2.265-2.266 2.265-1.252 0-2.265-1.014-2.265-2.265z',
  medium:     'M13.54 12a6.8 6.8 0 0 1-6.77 6.82A6.8 6.8 0 0 1 0 12a6.8 6.8 0 0 1 6.77-6.82A6.8 6.8 0 0 1 13.54 12zM20.96 12c0 3.54-1.51 6.42-3.38 6.42-1.87 0-3.39-2.88-3.39-6.42s1.52-6.42 3.39-6.42 3.38 2.88 3.38 6.42M24 12c0 3.17-.53 5.75-1.19 5.75-.66 0-1.19-2.58-1.19-5.75s.53-5.75 1.19-5.75C23.47 6.25 24 8.83 24 12z',
  spotify:    'M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z',
  telegram:   'M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z',
  snapchat:   'M12.206.793c.99 0 4.347.276 5.93 3.821.529 1.193.403 3.219.299 4.847l-.003.06c-.006.09-.01.18-.013.27.18.045.38.094.574.095.396.002.78-.08 1.06-.397a.7.7 0 0 1 .13-.116c.034-.02.068-.039.105-.053a.45.45 0 0 1 .156-.025c.135 0 .283.049.48.179.311.198.374.403.343.578-.053.286-.43.515-.642.625-.03.015-.066.032-.109.053-.203.1-.614.302-.638.82-.01.207.011.49.187.794.045.077.65 1.516 2.392 1.977.171.047.285.159.293.325.02.377-.867.706-1.038.767-.034.012-.055.024-.059.034-.007.012.018.079.038.12.232.482.55.85.9 1.18.35.329.733.539.914.609.082.032.16.039.24.036.07-.003.14-.014.22-.022.202-.023.395-.046.584-.016.228.037.41.139.56.309.15.17.232.38.232.59 0 .47-.39.823-.812.945-.27.078-.56.108-.895.145-.33.037-.698.082-1.14.216-.17.051-.378.178-.578.317-.374.258-.789.546-1.427.546-.276 0-.538-.063-.84-.127-.468-.101-.994-.216-1.766-.216-1.01 0-1.77.215-2.35.443-.566.225-1.05.48-1.5.48-.48 0-.96-.243-1.52-.47-.583-.227-1.35-.457-2.39-.457-.762 0-1.277.114-1.744.215-.303.065-.565.127-.84.127-.633 0-1.05-.28-1.42-.54-.198-.139-.408-.265-.578-.316-.437-.133-.808-.178-1.138-.216-.335-.036-.625-.066-.895-.144-.423-.122-.813-.476-.813-.945 0-.21.082-.42.232-.59.15-.17.332-.271.56-.31.19-.03.383-.006.584.017.08.009.15.02.22.022.08.003.158-.004.24-.036.185-.07.565-.28.916-.61.35-.33.668-.698.9-1.18.02-.04.045-.11.038-.12a.16.16 0 0 0-.061-.033c-.171-.061-1.059-.39-1.038-.766.008-.166.12-.278.292-.325 1.742-.46 2.346-1.9 2.39-1.977.176-.304.197-.588.187-.794-.024-.518-.435-.72-.638-.82a2.65 2.65 0 0 1-.108-.053c-.213-.11-.59-.34-.643-.625-.03-.175.033-.38.344-.578.197-.13.345-.178.48-.178a.449.449 0 0 1 .255.077c.034.02.067.05.1.115.28.316.662.398 1.058.396.194-.001.394-.05.574-.095L8.12 9.5c-.106-1.63-.232-3.658.297-4.852C9.854 1.068 13.21.793 14.2.793h-.005l-.001-.001h.012z',
  pinterest:  'M12 0C5.373 0 0 5.372 0 12c0 5.084 3.163 9.426 7.627 11.174-.105-.949-.2-2.405.042-3.441.218-.937 1.407-5.965 1.407-5.965s-.359-.719-.359-1.782c0-1.668.967-2.914 2.171-2.914 1.023 0 1.518.769 1.518 1.69 0 1.029-.655 2.568-.994 3.995-.283 1.194.599 2.169 1.777 2.169 2.133 0 3.772-2.249 3.772-5.495 0-2.873-2.064-4.882-5.012-4.882-3.414 0-5.418 2.561-5.418 5.207 0 1.031.397 2.138.893 2.738a.36.36 0 0 1 .083.345l-.333 1.36c-.053.22-.174.267-.402.161-1.499-.698-2.436-2.889-2.436-4.649 0-3.785 2.75-7.262 7.929-7.262 4.163 0 7.398 2.967 7.398 6.931 0 4.136-2.607 7.464-6.227 7.464-1.216 0-2.359-.632-2.75-1.378l-.748 2.853c-.271 1.043-1.002 2.35-1.492 3.146C9.57 23.812 10.763 24 12 24c6.627 0 12-5.373 12-12S18.627 0 12 0z',
  soundcloud: 'M1.175 12.225C.692 12.225 0 12.653 0 13.16v.238c0 .51.692.925 1.175.925.483 0 1.173-.415 1.173-.925v-.238c0-.507-.69-.935-1.173-.935zm1.68-2.67c0-.41-.42-.773-.906-.773-.487 0-.9.364-.9.773v3.586c0 .41.413.773.9.773.486 0 .906-.364.906-.773V9.555zm2.63-2.247c0-.405-.32-.73-.72-.73-.4 0-.723.325-.723.73v5.833c0 .405.322.73.722.73.4 0 .72-.325.72-.73V7.308zm2.653-.793c0-.418-.326-.753-.728-.753-.402 0-.728.335-.728.753v6.626c0 .418.326.753.728.753.402 0 .728-.335.728-.753V6.515zm2.63-.247c0-.416-.326-.75-.728-.75-.402 0-.728.334-.728.75v7.02c0 .416.326.75.728.75.402 0 .728-.334.728-.75V6.268zm2.652.267c0-.416-.326-.75-.728-.75-.402 0-.728.334-.728.75v6.793c0 .416.326.75.728.75.402 0 .728-.334.728-.75V6.535zm5.333 2.04c-.196 0-.392.026-.58.071-.186-1.989-1.86-3.54-3.895-3.54-1.078 0-2.05.43-2.763 1.12v9.155c0 .41.32.74.73.74h6.51c1.338 0 2.42-1.082 2.42-2.42 0-1.339-1.082-2.126-2.422-2.126z',
  vimeo:      'M23.9765 6.4168c-.105 2.338-1.739 5.5429-4.894 9.6088-3.2679 4.247-6.0258 6.3699-8.2898 6.3699-1.409 0-2.578-1.294-3.553-3.881L5.9384 14.4629c-.729-2.592-1.502-3.88-2.312-3.88-.179 0-.806.378-1.895 1.132L0 10.492c1.198-1.047 2.377-2.101 3.535-3.149C5.064 6.0498 6.2 5.3278 6.929 5.2628c1.842-.178 2.976.1.498 3.8248l1.444 5.8599.001.031c.46 2.07 1.009 3.105 1.54 3.105.438 0 1.093-.692 1.974-2.082 1.158-1.833 2.143-3.238 2.145-3.24.809-1.375 1.229-2.422 1.268-3.144.108-1.168-.42-1.757-1.59-1.757-.567 0-1.198.132-1.891.384 1.12-3.6659 3.252-5.4469 6.396-5.3629 2.336.066 3.441 1.5419 3.334 4.4149z',
  flickr:     'M0 12c0 3.074 2.494 5.564 5.565 5.564 3.075 0 5.569-2.49 5.569-5.564S8.64 6.436 5.565 6.436C2.495 6.436 0 8.926 0 12zm12.866 0c0 3.074 2.493 5.564 5.567 5.564C21.496 17.564 24 15.074 24 12s-2.504-5.564-5.567-5.564c-3.074 0-5.567 2.49-5.567 5.564z',
  docker:     'M13.983 11.078h2.119a.186.186 0 0 0 .186-.185V9.006a.186.186 0 0 0-.186-.186h-2.119a.185.185 0 0 0-.185.185v1.888c0 .102.083.185.185.185m-2.954-5.43h2.118a.186.186 0 0 0 .186-.186V3.574a.186.186 0 0 0-.186-.185h-2.118a.185.185 0 0 0-.185.185v1.888c0 .102.082.185.185.185m0 2.716h2.118a.187.187 0 0 0 .186-.186V6.29a.186.186 0 0 0-.186-.185h-2.118a.185.185 0 0 0-.185.185v1.887c0 .102.082.185.185.186m-2.93 0h2.12a.186.186 0 0 0 .184-.186V6.29a.185.185 0 0 0-.185-.185H8.1a.185.185 0 0 0-.185.185v1.887c0 .102.083.185.185.186m-2.964 0h2.119a.186.186 0 0 0 .185-.186V6.29a.185.185 0 0 0-.185-.185H5.136a.186.186 0 0 0-.186.185v1.887c0 .102.084.185.186.186m5.893 2.715h2.118a.186.186 0 0 0 .186-.185V9.006a.186.186 0 0 0-.186-.186h-2.118a.185.185 0 0 0-.185.185v1.888c0 .102.082.185.185.185m-2.93 0h2.12a.185.185 0 0 0 .184-.185V9.006a.184.184 0 0 0-.185-.186h-2.12a.185.185 0 0 0-.184.185v1.888c0 .102.083.185.185.185m-2.964 0h2.119a.185.185 0 0 0 .185-.185V9.006a.185.185 0 0 0-.185-.186h-2.12a.186.186 0 0 0-.186.186v1.887c0 .102.084.185.186.185m-2.92 6.674c1.11 0 2.07.556 2.645 1.395.596-.253 1.246-.394 1.93-.394 2.817 0 5.1 2.284 5.1 5.1 0 .283-.023.561-.066.832H0v-.012C0 17.23 2.22 14.988 4.94 14.988',
  npm:        'M1.763 0C.786 0 0 .786 0 1.763v20.474C0 23.214.786 24 1.763 24h20.474c.977 0 1.763-.786 1.763-1.763V1.763C24 .786 23.214 0 22.237 0zM5.13 5.323l13.837.019-.009 13.836h-3.464l.01-10.382h-3.456L12.04 19.17H5.113z',
  pypi:       'M11.977.006c-.386 0-.764.024-1.125.07L8.94.39C5.928.84 5.37 1.86 5.37 4.06v2.28h6.64v.76H3.53c-2.34 0-4.387 1.407-5.027 4.08-.74 3.075-.77 4.994 0 8.212.57 2.39 1.93 4.08 4.27 4.08h2.76v-2.738c0-2.658 2.3-5.001 5.027-5.001h6.626c2.238 0 4.023-1.842 4.023-4.089V4.058c0-2.182-1.841-3.818-4.023-4.005A28.06 28.06 0 0 0 13.48 0h-1.503zm-3.59 2.218a1.248 1.248 0 1 1 0 2.496 1.248 1.248 0 0 1 0-2.496zm11.58 7.56h2.76c2.34 0 3.74 1.69 4.28 4.08.77 3.218.74 5.137 0 8.212-.57 2.39-1.938 4.08-4.28 4.08h-2.76v-2.738c0-2.658-2.3-5.001-5.027-5.001H8.314c-2.238 0-4.023-1.842-4.023-4.089v-2.238c0-2.236 1.785-4.08 4.023-4.08h4.273c2.728 0 5.026-2.344 5.026-5.002H8.314zm1.25 5.28a1.248 1.248 0 1 1 0 2.496 1.248 1.248 0 0 1 0-2.496z',
  mastodon:   'M23.268 5.313c-.35-2.578-2.617-4.61-5.304-5.004C17.51.242 15.792 0 11.813 0h-.03c-3.98 0-4.835.242-5.288.309C3.882.692 1.496 2.518.917 5.127.64 6.412.61 7.837.661 9.143c.074 1.874.088 3.745.26 5.611.118 1.24.325 2.47.62 3.68.55 2.237 2.777 4.098 4.96 4.857 2.336.792 4.849.923 7.256.38.265-.061.527-.132.786-.213.585-.184 1.27-.39 1.774-.753a.057.057 0 0 0 .023-.043v-1.809a.052.052 0 0 0-.02-.041.053.053 0 0 0-.046-.01 20.282 20.282 0 0 1-4.709.545c-2.73 0-3.463-1.284-3.674-1.818a5.593 5.593 0 0 1-.319-1.433.053.053 0 0 1 .066-.054c1.517.363 3.072.546 4.632.546.376 0 .75 0 1.125-.01 1.57-.044 3.224-.124 4.768-.422.038-.008.077-.015.11-.024 2.435-.464 4.753-1.92 4.989-5.604.008-.145.03-1.52.03-1.67.002-.512.167-3.63-.024-5.545zm-3.748 9.195h-2.561V8.29c0-1.309-.55-1.976-1.67-1.976-1.23 0-1.846.79-1.846 2.35v3.403h-2.546V8.663c0-1.56-.617-2.35-1.848-2.35-1.112 0-1.668.668-1.67 1.977v6.218H4.822V8.102c0-1.31.337-2.35 1.011-3.12.696-.77 1.608-1.164 2.74-1.164 1.311 0 2.302.5 2.962 1.498l.638 1.06.638-1.06c.66-.999 1.65-1.498 2.96-1.498 1.13 0 2.043.395 2.74 1.164.675.77 1.012 1.81 1.012 3.12z',
  keybase:    'M10.888 14.408l-3.026 3.026.643 2.572-2.572-.643-1.028 1.028 2.572.643-.643 2.572 2.572-.643 3.026-3.026-1.544-5.529zm9.826-12.582a2.186 2.186 0 0 0-3.09 0l-3.737 3.737-1.286-1.286-1.544 1.544 1.286 1.286-6.954 6.954 5.53 1.543 6.954-6.954 1.286 1.286 1.544-1.543-1.286-1.286 3.737-3.737a2.186 2.186 0 0 0 0-3.09l-.44-.454z',
  devdot:     'M7.826 10.083a.784.784 0 0 0-.468-.175h-.701v4.198h.701a.786.786 0 0 0 .469-.175c.155-.117.233-.292.233-.525v-2.798c.001-.233-.079-.408-.234-.525zM19.236 3H4.764C3.791 3 3.002 3.787 3 4.76v14.48c.002.973.791 1.76 1.764 1.76h14.473c.973 0 1.762-.787 1.763-1.76V4.76A1.763 1.763 0 0 0 19.236 3zm-9.443 9.663c0 .655-.24 1.169-.717 1.541-.479.371-1.066.558-1.765.565H5.587V9.087h1.724c.727 0 1.324.195 1.79.583.466.388.695.892.692 1.515v2.478zm3.322 2.106c0 .538-.419.834-.827.834-.349 0-.795-.193-.795-.834v-4.198c0-.538.42-.833.795-.833.348 0 .827.193.827.833v4.198zm3.22-.021c0 .519-.38.861-.917.861-.504 0-.87-.34-.917-.861V9.13c0-.519.38-.86.917-.86.504 0 .87.34.917.86v5.618z',
  hackernews: 'M0 24V0h24v24H0zM6.951 5.896l4.112 7.708v5.064h1.583v-4.972l4.148-7.799h-1.749l-3.156 6.571-.026.026-3.155-6.598z',
  discord:    'M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057.106 18.1.131 18.14.163 18.165a19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03z',
  xbox:       'M4.038 5.489c.084-.101.17-.2.258-.297C5.743 3.676 7.615 2.643 9.773 2.234a.24.24 0 0 1 .26.134L12 6.226l1.967-3.858a.24.24 0 0 1 .26-.134c2.158.41 4.03 1.441 5.477 2.958.088.097.174.196.258.297A12.02 12.02 0 0 1 23.97 11.8a.241.241 0 0 1-.057.178l-5.55 6.296a.242.242 0 0 1-.378-.02L12 9.62l-5.985 8.633a.242.242 0 0 1-.378.02L.087 11.978A.241.241 0 0 1 .03 11.8a12.02 12.02 0 0 1 4.008-6.31z',
};

// Map platform name → icon key in _SI
function _socialIconPath(name) {
  const n = name.toLowerCase();
  if (n.includes('github'))           return _SI.github;
  if (n.includes('gitlab'))           return _SI.gitlab;
  if (n.includes('twitter') || n === 'x' || n.includes('/ x')) return _SI.x;
  if (n.includes('instagram'))        return _SI.instagram;
  if (n.includes('tiktok'))           return _SI.tiktok;
  if (n.includes('reddit'))           return _SI.reddit;
  if (n.includes('linkedin'))         return _SI.linkedin;
  if (n.includes('youtube'))          return _SI.youtube;
  if (n.includes('twitch'))           return _SI.twitch;
  if (n.includes('steam'))            return _SI.steam;
  if (n.includes('medium'))           return _SI.medium;
  if (n.includes('spotify'))          return _SI.spotify;
  if (n.includes('telegram'))         return _SI.telegram;
  if (n.includes('snapchat'))         return _SI.snapchat;
  if (n.includes('pinterest'))        return _SI.pinterest;
  if (n.includes('soundcloud'))       return _SI.soundcloud;
  if (n.includes('vimeo'))            return _SI.vimeo;
  if (n.includes('flickr'))           return _SI.flickr;
  if (n.includes('docker'))           return _SI.docker;
  if (n.includes('npm'))              return _SI.npm;
  if (n.includes('pypi') || n.includes('python')) return _SI.pypi;
  if (n.includes('mastodon'))         return _SI.mastodon;
  if (n.includes('keybase'))          return _SI.keybase;
  if (n.includes('dev.to') || n.includes('devto')) return _SI.devdot;
  if (n.includes('hacker'))           return _SI.hackernews;
  return null;
}

function _socialIconEl(platform) {
  const path = _socialIconPath(platform);
  if (path) {
    return '<svg class="social-card-svg" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="' + path + '"/></svg>';
  }
  const init = platform.split(/[\s\/]+/).filter(Boolean).slice(0, 2).map(w => w[0] || '').join('').toUpperCase().slice(0, 2);
  return '<span class="social-card-init" aria-hidden="true">' + esc(init) + '</span>';
}

// Returns true only for values worth having a copy button (filters out enum labels, booleans, snake_case internals)
function _shouldShowCopy(val) {
  if (val.length < 3) return false;
  if (/^(yes|no|true|false)$/i.test(val)) return false;
  if (/^[A-Z][A-Z_0-9]{2,}$/.test(val)) return false;       // ALL_CAPS_ENUM
  if (/^[a-z][a-z_0-9]{2,}$/.test(val) && !val.includes(' ')) return false; // snake_case_label
  return true;
}

// Extracts the username from a social profile URL (last meaningful path segment)
function _extractSocialUsername(url) {
  if (!url) return null;
  try {
    const u = new URL(url);
    const parts = u.pathname.replace(/\/$/, '').split('/').filter(Boolean);
    if (parts[0] === 'user' && parts[1]) return parts[1]; // Reddit: /user/username
    if (parts[0]) return parts[0];
  } catch {}
  return null;
}

// Returns unavatar.io URL for supported platforms, null otherwise
function _unavatarUrl(platform, username) {
  if (!username) return null;
  const p = platform.toLowerCase();
  let service = null;
  if      (p.includes('github'))                                      service = 'github';
  else if (p.includes('gitlab'))                                      service = 'gitlab';
  else if (p.includes('twitter') || p === 'x' || p.includes('/ x')) service = 'twitter';
  else if (p.includes('instagram'))                                   service = 'instagram';
  else if (p.includes('tiktok'))                                      service = 'tiktok';
  else if (p.includes('reddit'))                                      service = 'reddit';
  else if (p.includes('youtube'))                                     service = 'youtube';
  else if (p.includes('twitch'))                                      service = 'twitch';
  else if (p.includes('telegram'))                                    service = 'telegram';
  else if (p.includes('spotify'))                                     service = 'spotify';
  else if (p.includes('pinterest'))                                   service = 'pinterest';
  else if (p.includes('linkedin'))                                    service = 'linkedin';
  else if (p.includes('soundcloud'))                                  service = 'soundcloud';
  if (!service) return null;
  return 'https://unavatar.io/' + service + '/' + encodeURIComponent(username);
}

// ── Render results entry point ───────────────────────
function renderResults() {
  const o = currentResult.oathnet;
  const s = currentResult.sherlock;
  const q = currentResult.query;

  const nBreach  = o ? o.breach_count  : 0;
  const nStealer = o ? o.stealer_count : 0;
  const nSocial  = s ? s.found_count   : 0;
  const nHolehe  = o ? o.holehe_count  : 0;
  const nTotal   = nBreach + nStealer + nSocial + nHolehe;

  const risk = Math.min(nBreach*15 + nStealer*20 + nHolehe*3, 100);
  const [rl, rc] = riskLabel(risk);

  // Header
  document.getElementById('resTarget').textContent = q;
  document.getElementById('resSub').textContent =
    `${nTotal} results found · ${currentResult.elapsed || 0}s · ${currentResult.timestamp?.slice(0,16) || ''}`;
  document.getElementById('riskBadge').textContent = `${risk} — ${rl}`;
  document.getElementById('riskBadge').style.cssText =
    `background:${rc}18;border:1px solid ${rc}44;color:${rc}`;

  // Stat grid — Phase 17: clickable jump + risk tinting + correct token refs
  const grid = document.getElementById('statGrid');
  grid.innerHTML = [
    {val:nTotal,   lbl:'Total Found', bar:'var(--color-accent)',   panel:'',             risk:'',
     note:''},
    {val:nBreach,  lbl:'Breaches',    bar:'var(--color-critical)', panel:'panelBreach',
     risk: nBreach>10?'risk-critical':nBreach>0?'risk-high':'',
     note: nBreach>10?'⚠ High risk':nBreach>0?'⚠ Attention':'✓ Clean',
     nc:   nBreach>10?'var(--color-critical)':nBreach>0?'var(--color-high)':'var(--color-success)'},
    {val:nStealer, lbl:'Stolen Info', bar:'var(--color-high)',     panel:'panelStealer',
     risk: nStealer>0?'risk-critical':'',
     note: nStealer>0?'🚨 Compromised':'✓ Clean',
     nc:   nStealer>0?'var(--color-critical)':'var(--color-success)'},
    {val:nSocial,  lbl:'Social',      bar:'var(--color-info)',     panel:'panelSocial',
     risk: nSocial>0?'risk-found':'',
     note: `${s?.total_checked||0} checked`},
    {val:nHolehe,  lbl:'Email Svcs',  bar:'#9b59b6',              panel:'panelEmail',
     risk: nHolehe>0?'risk-found':'',
     note:''},
  ].map((c, i) => {
    const attrs = c.panel
      ? ` data-action="jump-to-panel" data-panel="${c.panel}" role="button" tabindex="0"`
      : '';
    return `
    <div class="stat-card animated${c.risk ? ' '+c.risk : ''}"${attrs} style="animation-delay:${i * 0.07}s">
      <div class="stat-card-bar" style="background:${c.bar}"></div>
      <div class="stat-card-val">${c.val}</div>
      <div class="stat-card-lbl">${c.lbl}</div>
      ${c.note ? `<div class="stat-card-note" style="color:${c.nc||'var(--color-text-tertiary)'};">${c.note}</div>` : ''}
      ${c.panel ? '<div class="stat-card-jump">↓ view</div>' : ''}
    </div>`;
  }).join('');

  // Apply panel visibility based on modules that ran
  applyPanelVisibility();

  // Render content
  renderBreaches(o);
  renderStealers(o);
  renderSocial(s);
  renderHolehe(o);
  renderExtras();


  document.getElementById('results').classList.add('visible');
  document.getElementById('results').scrollIntoView({behavior:'smooth', block:'start'});
}

// ── Breach severity helper ───────────────────────────
function breachSeverity(b) {
  if (b.password && b.password !== '─' && b.password !== '') return 'critical';
  if (b.email    && b.email    !== '─' && b.email    !== '') return 'high';
  if (b.username && b.username !== '─' && b.username !== '') return 'medium';
  return 'low';
}

// ── Breaches ─────────────────────────────────────────
function renderBreaches(o) {
  breachPage = 0;
  pwdVisible = {};
  const el    = document.getElementById('breachBody');
  const badge = document.getElementById('breachBadge');
  const panel = document.getElementById('panelBreach');
  if (!o || !o.breaches || o.breaches.length === 0) {
    if (panel) panel.style.display = 'none';
    badge.textContent = '0';
    el.innerHTML = '<div style="color:var(--green);font-family:var(--mono);font-size:.8rem">✓ No breaches found.</div>';
    return;
  }
  if (panel) panel.style.display = '';
  badge.textContent = o.breach_count;
  _renderBreachPage(o, el);
}

function _renderBreachPage(o, el) {
  const end     = (breachPage + 1) * BREACH_PAGE_SIZE;
  const rows    = o.breaches.slice(0, end);
  const hasMore = o.breaches.length > end;
  const total   = o.breach_count;

  // Build a single key-value field cell
  const mkField = (key, val, cls, isExtra) => {
    if (!val || val === '─' || val === '') return '';
    const valStr = String(val);
    return '<div class="breach-field' + (isExtra ? ' extra-field' : '') + '">'
      + '<span class="breach-field-key">' + esc(key) + '</span>'
      + '<div class="breach-field-row">'
      + '<span class="breach-field-val' + (cls ? ' ' + cls : '') + '">' + esc(valStr) + '</span>'
      + (!isExtra || _shouldShowCopy(valStr) ? '<button class="btn-copy btn-xs" data-action="copy-field" data-val="' + escAttr(valStr) + '">copy</button>' : '')
      + '</div></div>';
  };

  const cards = rows.map((b, i) => {
    const sev    = breachSeverity(b);
    const hasPwd = b.password && b.password !== '─' && b.password !== '';
    const pwdId  = 'pwd_' + i;
    const isVis  = pwdVisible[pwdId];

    // Password field — keep existing masked-toggle pattern + copy btn
    let pwdField = '';
    if (hasPwd) {
      const plain = b.password;
      pwdField = '<div class="breach-field">'
        + '<span class="breach-field-key">Password</span>'
        + '<div class="breach-field-row">'
        + '<div class="pwd-cell">'
        + '<span class="pwd-text ' + (isVis ? '' : 'masked') + '" id="' + pwdId + '">' + (isVis ? esc(plain) : '••••••••') + '</span>'
        + '<button class="pwd-toggle" data-action="toggle-pwd" data-pwdid="' + pwdId + '" data-plain="' + escAttr(plain) + '">' + (isVis ? '🙈' : '👁') + '</button>'
        + '</div>'
        + '<button class="btn-copy btn-xs" data-action="copy-field" data-val="' + escAttr(plain) + '">copy</button>'
        + '</div></div>';
    }

    // Core fields (display order: pwd handled above, then rest)
    const coreHtml = pwdField
      + mkField('Email',    b.email)
      + mkField('Username', b.username)
      + mkField('IP',       b.ip,        'val-muted')
      + mkField('Phone',    b.phone,     'val-muted')
      + mkField('Country',  b.country,   'val-muted')
      + mkField('Discord',  b.discord_id, 'val-accent');

    // Extra fields — skip internal keys, null, empty, or nested objects
    const extra = b.extra || {};
    const extraKeys = Object.keys(extra).filter(k =>
      !k.startsWith('_') &&
      extra[k] !== null && extra[k] !== undefined &&
      extra[k] !== '' &&
      typeof extra[k] !== 'object'
    );
    const extraHtml = extraKeys.length > 0
      ? '<div class="breach-extra-label">extra fields</div>'
        + extraKeys.map(k => mkField(k.replace(/_/g, ' '), extra[k], '', true)).join('')
      : '';

    const date = (b.date || '').slice(0, 10);
    return '<div class="breach-card sev-' + sev + '">'
      + '<div class="breach-card-header">'
      + '<span class="sev-breach-badge">' + sev + '</span>'
      + '<span class="breach-card-dbname">' + esc(b.dbname) + '</span>'
      + (date ? '<span class="breach-card-date">' + esc(date) + '</span>' : '')
      + '</div>'
      + '<div class="breach-card-fields">' + coreHtml + extraHtml + '</div>'
      + '</div>';
  }).join('');

  el.innerHTML = '<div class="breach-grid">' + cards + '</div>'
    + '<div style="display:flex;align-items:center;justify-content:space-between;margin-top:10px;font-family:var(--mono);font-size:.7rem;color:var(--text3)">'
    + '<span>Showing ' + rows.length + ' of ' + total.toLocaleString()
    + (currentResult.breachCursor ? ' (API: ' + currentResult.breachTotal.toLocaleString() + ' total)' : '') + '</span>'
    + '<button class="btn-copy btn-xs" data-action="reveal-all-passwords">👁 Reveal All</button>'
    + '</div>'
    + (hasMore || currentResult.breachCursor
      ? '<button class="load-more-btn" data-action="load-more-breaches">↓ Load more · ' + total.toLocaleString() + ' total</button>'
      : '');
}

function togglePwd(id, plain) {
  pwdVisible[id] = !pwdVisible[id];
  const el = document.getElementById(id);
  if (!el) return;
  if (pwdVisible[id]) {
    el.textContent = plain;
    el.classList.remove('masked');
    if (el.nextElementSibling) el.nextElementSibling.textContent = '🙈';
  } else {
    el.textContent = '••••••••';
    el.classList.add('masked');
    if (el.nextElementSibling) el.nextElementSibling.textContent = '👁';
  }
}

function revealAllPasswords() {
  const o = currentResult.oathnet;
  if (!o?.breaches) return;
  o.breaches.forEach((b, i) => {
    if (b.password && b.password !== '─') {
      const id = 'pwd_' + i;
      pwdVisible[id] = true;
      const el = document.getElementById(id);
      if (el) {
        el.textContent = b.password;
        el.classList.remove('masked');
        if (el.nextElementSibling) el.nextElementSibling.textContent = '🙈';
      }
    }
  });
}

async function loadMoreBreaches() {
  const o      = currentResult.oathnet;
  const cursor = currentResult.breachCursor;
  const query  = currentResult.query;
  const btn    = document.querySelector('.load-more-btn');

  // If we still have local data to show, paginate locally first
  const shownCount = (breachPage + 1) * BREACH_PAGE_SIZE;
  if (shownCount < (o.breaches || []).length) {
    breachPage++;
    const el = document.getElementById('breachBody');
    _renderBreachPage(o, el);
    return;
  }

  // Local data exhausted — fetch next page from API
  if (!cursor || !query) return;

  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ Loading from API…';
  }

  try {
    const r = await apiFetch('/api/search/more-breaches', {
      method: 'POST',
      body: JSON.stringify({ query, cursor }),
    });

    if (!r.ok) {
      showToast('Failed to load more breaches', true);
      if (btn) { btn.disabled = false; btn.textContent = '↓ Retry'; }
      return;
    }

    const data = await r.json();
    const newBreaches = data.breaches || [];

    if (newBreaches.length === 0) {
      if (btn) { btn.textContent = '✓ All results loaded'; btn.disabled = true; }
      return;
    }

    // Append to existing breaches
    o.breaches       = [...(o.breaches || []), ...newBreaches];
    o.breach_count   = data.results_found || o.breach_count;
    currentResult.breachCursor = data.next_cursor || '';

    breachPage++;
    const el = document.getElementById('breachBody');
    _renderBreachPage(o, el);

    showToast(`Loaded ${newBreaches.length} more breaches`);
  } catch(e) {
    showToast('Error: ' + e.message, true);
    if (btn) { btn.disabled = false; btn.textContent = '↓ Retry'; }
  }
}

// ── Stealers ─────────────────────────────────────────
function renderStealers(o) {
  const el = document.getElementById('stealerBody');
  const badge = document.getElementById('stealerBadge');
  const panel = document.getElementById('panelStealer');
  if (!o || !o.stealers || o.stealers.length === 0) {
    if (panel) panel.style.display = 'none';
    badge.textContent = '0';
    el.innerHTML = `<div style="color:var(--green);font-family:var(--mono);font-size:.8rem">✓ No stealer logs found.</div>`;
    return;
  }
  if (panel) panel.style.display = '';
  badge.textContent = o.stealer_count;
  el.innerHTML = `
    <div style="color:var(--red);font-family:var(--mono);font-size:.78rem;margin-bottom:12px;padding:8px 12px;background:var(--red-lo);border:1px solid rgba(232,64,64,.2);border-radius:6px">
      🚨 Credentials found in malware stealer logs. A device may be compromised.
    </div>
    <table class="data-table">
      <thead><tr><th>URL</th><th>Username</th><th>Domain</th><th>Date</th></tr></thead>
      <tbody>${o.stealers.slice(0,50).map(s => `
        <tr>
          <td style="max-width:200px">${esc((s.url||'').slice(0,60))}</td>
          <td class="val-amber">${esc(s.username)}</td>
          <td>${esc((s.domain||[]).slice(0,2).join(', '))}</td>
          <td class="val-muted">${esc((s.pwned_at||'').slice(0,10))}</td>
        </tr>`).join('')}
      </tbody>
    </table>`;
}

// ── Inline filter helper (Phase 16) ──────────────────
// Attaches a debounced input listener to .panel-filter inside bodyEl.
// itemSelector: which child elements to show/hide.
// getText: function(el) → string to match against.
function _attachFilter(bodyEl, itemSelector, getText) {
  const input = bodyEl.querySelector('.panel-filter');
  if (!input) return;
  let _t;
  input.addEventListener('input', function () {
    clearTimeout(_t);
    const q = this.value.toLowerCase().trim();
    _t = setTimeout(() => {
      const items = bodyEl.querySelectorAll(itemSelector);
      let shown = 0;
      items.forEach(item => {
        const match = !q || getText(item).toLowerCase().includes(q);
        item.style.display = match ? '' : 'none';
        if (match) shown++;
      });
      let noRes = bodyEl.querySelector('.filter-no-results');
      if (shown === 0 && q) {
        if (!noRes) {
          noRes = document.createElement('p');
          noRes.className = 'filter-no-results';
          bodyEl.appendChild(noRes);
        }
        noRes.textContent = 'No matches for "' + q + '"';
      } else if (noRes) {
        noRes.remove();
      }
    }, 150);
  });
}

// ── Social profiles ───────────────────────────────────
function renderSocial(s) {
  const el    = document.getElementById('socialBody');
  const badge = document.getElementById('socialBadge');
  const panel = document.getElementById('panelSocial');
  if (!s || !s.found || s.found.length === 0) {
    if (panel) panel.style.display = 'none';
    badge.textContent = '0';
    el.innerHTML = '<div style="color:var(--color-text-tertiary);font-family:var(--font-data);font-size:.8rem">No profiles found.</div>';
    return;
  }
  if (panel) panel.style.display = '';
  badge.textContent = s.found_count;

  const cards = s.found.map(p => {
    const url        = sanitizeUrl(p.url);
    const username   = _extractSocialUsername(p.url);
    const avatarUrl  = _unavatarUrl(p.platform, username);
    const iconHtml   = _socialIconEl(p.platform);

    // Avatar: img + fallback (fallback shown via JS error handler, not inline onerror — CSP-safe)
    const avatarHtml = avatarUrl
      ? '<img class="social-card-avatar" src="' + avatarUrl + '" alt="" loading="lazy">'
        + '<div class="social-card-avatar-fallback">' + iconHtml + '</div>'
      : '<div class="social-card-avatar-fallback" style="display:flex">' + iconHtml + '</div>';

    return '<div class="social-card">'
      + '<div class="social-card-header">'
      + '<div class="social-card-platform">'
      + '<div class="social-card-icon">' + iconHtml + '</div>'
      + '<span class="social-card-name">' + esc(p.platform) + '</span>'
      + '</div>'
      + (p.category ? '<span class="social-card-cat">' + esc(p.category) + '</span>' : '')
      + '</div>'
      + '<div class="social-card-body">'
      + '<div class="social-card-avatar-wrap">' + avatarHtml + '</div>'
      + (username ? '<div class="social-card-username">@' + esc(username) + '</div>' : '')
      + '</div>'
      + '<a class="social-card-cta" href="' + url + '" target="_blank" rel="noopener noreferrer">'
      + 'View Profile \u2192'
      + '</a>'
      + '</div>';
  }).join('');

  const filterHtml = s.found.length > 10
    ? '<input class="panel-filter" type="text" placeholder="Filter ' + s.found.length + ' platforms\u2026" aria-label="Filter social platforms">'
    : '';

  el.innerHTML = filterHtml + '<div class="social-cards-grid">' + cards + '</div>';

  // Attach avatar error handlers (CSP-safe — no inline onerror attribute)
  el.querySelectorAll('.social-card-avatar').forEach(function(img) {
    img.addEventListener('error', function() {
      this.style.display = 'none';
      const fallback = this.nextElementSibling;
      if (fallback) fallback.style.display = 'flex';
    });
    // Handle already-failed cached 404s
    if (img.complete && !img.naturalWidth) img.dispatchEvent(new Event('error'));
  });

  if (filterHtml) {
    _attachFilter(el, '.social-card', c => (c.querySelector('.social-card-name')?.textContent || ''));
  }
}

// ── Holehe email registrations ────────────────────────
function renderHolehe(o) {
  const el = document.getElementById('emailBody');
  const badge = document.getElementById('emailBadge');
  const panel = document.getElementById('panelEmail');
  if (!o || !o.holehe_domains || o.holehe_domains.length === 0) {
    if (panel) panel.style.display = 'none';
    badge.textContent = '0';
    el.innerHTML = '<div style="color:var(--text3);font-family:var(--mono);font-size:.8rem">No email registrations found.</div>';
    return;
  }
  if (panel) panel.style.display = '';
  badge.textContent = o.holehe_count;

  const filterHtml = o.holehe_domains.length > 10
    ? '<input class="panel-filter" type="text" placeholder="Filter ' + o.holehe_domains.length + ' domains\u2026" aria-label="Filter email registrations">'
    : '';
  const chipsHtml = o.holehe_domains.map(d => '<span class="social-badge">' + esc(d) + '</span>').join('');

  el.innerHTML = filterHtml + '<div class="social-grid">' + chipsHtml + '</div>';

  if (filterHtml) {
    _attachFilter(el, '.social-badge', b => (b.textContent || ''));
  }
}

// ── Extras panel (IP, subdomains, Discord, gaming) ───
function renderExtras() {
  const el = document.getElementById('extrasBody');
  const parts = [];

  // IP Info
  const ip = currentResult.extras.ip;
  if (ip?.ok && ip.data) {
    const d = ip.data;
    parts.push(`<div style="margin-bottom:16px">
      <div class="section-label" style="margin-bottom:8px">IP Information</div>
      <table class="data-table" style="max-width:500px">
        <tr><th>Country</th><td>${esc(d.country)} (${esc(d.countryCode)})</td></tr>
        <tr><th>City</th><td>${esc(d.city)}</td></tr>
        <tr><th>ISP</th><td>${esc(d.isp)}</td></tr>
        <tr><th>Org</th><td>${esc(d.org)}</td></tr>
        <tr><th>ASN</th><td class="val-muted">${esc(d.as||d.asn||'─')}</td></tr>
        <tr><th>Proxy/VPN</th><td class="${d.proxy?'val-warn':'val-safe'}">${d.proxy?'⚠ Yes':'✓ No'}</td></tr>
        <tr><th>Hosting</th><td class="${d.hosting?'val-warn':'val-muted'}">${d.hosting?'⚠ Yes':'No'}</td></tr>
      </table>
    </div>`);
  }

  // Subdomains
  const subs = currentResult.extras.subdomains;
  if (subs?.ok && subs.data?.length) {
    parts.push(`<div>
      <div class="section-label" style="margin-bottom:8px">Subdomains (${subs.count})</div>
      <div style="font-family:var(--mono);font-size:.76rem;color:var(--text2);columns:3;column-gap:16px">
        ${subs.data.slice(0,90).map(d=>`<div>${esc(d)}</div>`).join('')}
      </div>
    </div>`);
  }

  // Discord — support multiple lookups (auto-extracted from breach)
  const discList = currentResult.extras.discords || (currentResult.extras.discord ? [currentResult.extras.discord] : []);
  for (const disc of discList) {
    if (!disc) continue;
    if (disc.error) {
      parts.push(`<div>
        <div class="section-label" style="margin-bottom:8px">Discord Lookup</div>
        <div style="background:var(--amber-lo);border:1px solid rgba(245,166,35,.2);border-radius:6px;padding:10px 14px;font-family:var(--mono);font-size:.76rem;color:var(--amber)">
          ⚠ ${esc(disc.error)}
          ${disc.hint ? `<div style="color:var(--text3);font-size:.68rem;margin-top:6px">${esc(disc.hint)}</div>` : ''}
        </div>
      </div>`);
      continue;
    }
    if (!disc.user) {
      parts.push(`<div>
        <div class="section-label" style="margin-bottom:8px">Discord Lookup${disc.query_id ? ` — ID ${esc(disc.query_id)}` : ''}</div>
        <div style="background:var(--amber-lo);border:1px solid rgba(245,166,35,.2);border-radius:6px;padding:10px 14px;font-family:var(--mono);font-size:.76rem;color:var(--amber)">
          ⚠ Discord profile not found or API quota exhausted.
        </div>
      </div>`);
      continue;
    }
    const u = disc.user;
    const histList = disc.history?.usernames || [];
    const safeAvatarUrl = sanitizeImageUrl(u.avatar_url);
    const avatarHtml = safeAvatarUrl
      ? `<img class="discord-avatar" src="${safeAvatarUrl}" alt="avatar" data-fallback="true">`
        + `<div class="discord-avatar-placeholder" style="display:none">💬</div>`
      : `<div class="discord-avatar-placeholder">💬</div>`;
    const safeBannerUrl = sanitizeImageUrl(u.banner_url);
    const bannerStyle = safeBannerUrl
      ? `class="discord-banner has-banner" style="background-image:url('${safeBannerUrl}')"`
      : `class="discord-banner"`;
    const histHtml = histList.length
      ? `<div class="discord-history-section">
           <div class="discord-history-label">Username History</div>
           ${histList.map(h => `
             <div class="discord-history-item">
               <span class="discord-history-name">${esc(h.username)}</span>
               <span class="discord-history-date">${esc((h.timestamp||'').slice(0,10))}</span>
             </div>`).join('')}
         </div>` : '';
    const badgesHtml = u.badges?.length
      ? `<div class="discord-badges">${u.badges.map(b=>`<span class="discord-badge">${esc(b)}</span>`).join('')}</div>` : '';

    const fmtDiscordDate = (raw) => {
      if (!raw) return '';
      const d = new Date(raw);
      if (isNaN(d.getTime())) return raw.slice(0, 10);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    };
    parts.push(`<div>
      <div class="section-label" style="margin-bottom:10px">Discord Profile</div>
      <div class="discord-card">
        ${safeBannerUrl ? `<div class="discord-banner has-banner" style="background-image:url('${safeBannerUrl}')"></div>` : ''}
        <div class="discord-card-inner">
          <div class="discord-avatar-wrap">${avatarHtml}</div>
          <div class="discord-card-content">
            <div class="discord-global-name">${esc(u.global_name || u.username || 'Unknown')}</div>
            <div class="discord-username">@${esc(u.username || '─')}</div>
            <div class="discord-id-row">
              <span>#</span>
              <span class="discord-id-val" data-action="copy-discord-id" data-id="${esc(u.id||'')}" data-toast="Discord ID copied" title="Click to copy">${esc(u.id || '─')}</span>
            </div>
            ${u.creation_date ? `<div class="discord-created">📅 ${esc(fmtDiscordDate(u.creation_date))}</div>` : ''}
            ${badgesHtml}
          </div>
        </div>
        ${histList.length ? `
        <div class="discord-history-section">
          <div class="discord-history-label">Username History (${histList.length})</div>
          <div class="discord-history-list">
            ${histList.map((h,i) => `
              <div class="discord-history-item">
                <span class="discord-history-name">${i===0?'<span style="color:var(--amber)">▶ </span>':''}${esc(h.username)}</span>
                <span class="discord-history-date">${esc((h.timestamp||'').slice(0,10))}</span>
              </div>`).join('')}
          </div>
        </div>` : ''}
        <div class="discord-card-footer">
          <a class="discord-view-btn" href="https://discord.com/users/${esc(u.id||'')}" target="_blank" rel="noopener">
            <svg viewBox="0 0 24 24" fill="currentColor" width="12" height="12" aria-hidden="true"><path d="${_SI.discord}"/></svg>
            View Discord Profile
          </a>
        </div>
      </div>
    </div>`);
  }

  // Steam
  const steam = currentResult.extras.steam;
  if (steam?.ok && steam.data) {
    const d = steam.data;
    const profile = d.response?.players?.[0] || d;
    if (profile.personaname) {
      const safeSteamUrl = sanitizeImageUrl(profile.profileurl);
      parts.push(`<div>
        <div class="section-label" style="margin-bottom:8px">Steam Profile</div>
        <div class="gaming-card">
          <div class="gaming-card-header">
            <span class="gaming-card-icon">🎮</span>
            <div>
              <div class="gaming-card-title">${esc(profile.personaname)}</div>
              <div class="gaming-card-sub">SteamID: ${esc(profile.steamid||'─')}</div>
            </div>
          </div>
          <div class="gaming-kv">
            <div class="gaming-kv-item">
              <span class="gaming-kv-key">Real Name</span>
              <span class="gaming-kv-val">${esc(profile.realname||'─')}</span>
            </div>
            <div class="gaming-kv-item">
              <span class="gaming-kv-key">Country</span>
              <span class="gaming-kv-val">${esc(profile.loccountrycode||'─')}</span>
            </div>
            <div class="gaming-kv-item">
              <span class="gaming-kv-key">Profile URL</span>
              <span class="gaming-kv-val" style="font-size:.7rem">
                ${safeSteamUrl ? `<a href="${safeSteamUrl}" target="_blank" style="color:var(--blue)">${esc(profile.profileurl.slice(0,40))}</a>` : '─'}
              </span>
            </div>
            <div class="gaming-kv-item">
              <span class="gaming-kv-key">Visibility</span>
              <span class="gaming-kv-val">${profile.communityvisibilitystate===3?'Public':'Private'}</span>
            </div>
          </div>
        </div>
      </div>`);
    }
  }

  // Xbox
  const xbox = currentResult.extras.xbox;
  if (xbox && !xbox.ok) {
    const xboxErr = xbox.data?.error || 'Xbox lookup failed — profile not found or API quota exhausted.';
    parts.push(`<div>
      <div class="section-label" style="margin-bottom:8px">Xbox Live</div>
      <div style="background:var(--amber-lo);border:1px solid rgba(245,166,35,.2);border-radius:6px;padding:10px 14px;font-family:var(--mono);font-size:.76rem;color:var(--amber)">
        ⚠ ${esc(xboxErr)}
      </div>
    </div>`);
  } else if (xbox?.ok && xbox.data) {
    const d   = xbox.data;
    const m   = d.meta?.meta || d.meta || {};
    const scr = d.meta?.scraper_data || {};
    const gamerscore  = scr.gamerscore || m.gamerscore || '';
    const tier        = m.accounttier  || m.accountTier || '';
    const rep         = m.xboxonerep   || m.xboxOneRep  || '';
    const gamesPlayed = scr.games_played ?? null;
    const gameHistory = scr.game_history || [];
    // Gamertag may be in different fields depending on API response shape
    const xboxName    = d.gamertag || d.Gamertag || d.username || (d.id && isNaN(Number(d.id)) ? d.id : '') || 'Unknown';
    const xboxXUID    = d.xuid || (d.id && !isNaN(Number(d.id)) ? d.id : '');
    const xboxSvg     = `<svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20" aria-hidden="true"><path d="${_SI.xbox}"/></svg>`;
    const safeXboxAvatar = sanitizeImageUrl(d.avatar);
    const xboxAvatarHtml = safeXboxAvatar
      ? `<img class="social-avatar" src="${safeXboxAvatar}" alt="avatar" style="width:48px;height:48px;border-radius:50%;object-fit:cover;flex-shrink:0" onerror="this.style.display='none'">`
      : '';
    parts.push(`<div>
      <div class="section-label" style="margin-bottom:8px">Xbox Live Profile</div>
      <div class="gaming-card">
        <div class="gaming-card-header">
          ${xboxAvatarHtml ? `<div style="margin-right:10px">${xboxAvatarHtml}</div>` : `<span class="gaming-card-icon" style="color:#107c10;display:flex">${xboxSvg}</span>`}
          <div style="flex:1">
            <div class="gaming-card-title">${esc(xboxName)}</div>
            ${xboxXUID ? `<div class="gaming-card-sub">XUID: ${esc(xboxXUID)}</div>` : ''}
          </div>
          ${gamerscore ? `<div style="text-align:right;font-family:var(--mono);font-size:.72rem">
            <div style="color:var(--amber);font-size:1rem;font-weight:700">${esc(String(gamerscore))}</div>
            <div style="color:var(--text3)">Gamerscore</div>
          </div>` : ''}
        </div>
        <div class="gaming-kv">
          ${tier ? `<div class="gaming-kv-item">
            <span class="gaming-kv-key">Tier</span>
            <span class="gaming-kv-val" style="color:${tier==='Gold'?'var(--amber)':tier==='Silver'?'var(--text2)':'var(--text3)'}">${esc(tier)}</span>
          </div>` : ''}
          ${rep ? `<div class="gaming-kv-item">
            <span class="gaming-kv-key">Reputation</span>
            <span class="gaming-kv-val">${esc(rep)}</span>
          </div>` : ''}
          ${gamesPlayed !== null ? `<div class="gaming-kv-item">
            <span class="gaming-kv-key">Games Played</span>
            <span class="gaming-kv-val">${esc(String(gamesPlayed))}</span>
          </div>` : ''}
        </div>
        ${gameHistory.length ? `<div style="border-top:1px solid var(--line);padding:10px 14px">
          <div class="gaming-kv-key" style="margin-bottom:8px">Recent Games</div>
          <div style="display:flex;flex-direction:column;gap:4px">
            ${gameHistory.slice(0,5).map(g => `<div style="display:flex;align-items:center;justify-content:space-between;font-family:var(--mono);font-size:.72rem;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.04)"><span style="color:var(--text)">${esc(g.title||'─')}</span><span style="color:var(--text3)">${g.completionPercentage!=null ? esc(String(g.completionPercentage))+'%' : ''}</span></div>`).join('')}
          </div>
        </div>` : ''}
        <div style="padding:10px 14px 14px">
          <a class="discord-view-btn" href="https://www.xbox.com/play/user/${esc(d.id||d.xuid||'')}"
             target="_blank" rel="noopener" style="font-size:.7rem;text-decoration:none">
            ↗ View Xbox Profile
          </a>
        </div>
      </div>
    </div>`);
  }

  // Roblox
  const roblox = currentResult.extras.roblox;
  if (roblox?.ok && roblox.data) {
    const d        = roblox.data;
    const rName    = d['Current Username'] || d.username   || d.name        || 'Unknown';
    const rId      = d['User ID']          || d.user_id    || d.id          || '';
    const rDisplay = d['Display Name']     || d.displayName|| rName;
    const rJoined  = (d['Join Date']       || d.created    || '').slice(0, 10);
    const rAvatar  = sanitizeImageUrl(d['Avatar URL'] || d.avatar || '');
    const rOldRaw  = d['Old Usernames'] || '';
    const rOldArr  = Array.isArray(rOldRaw) ? rOldRaw
                   : (rOldRaw && rOldRaw !== 'None') ? rOldRaw.split(',').map(s=>s.trim()).filter(Boolean) : [];
    const rDiscord = d.Discord || d.discord || '';
    const rBanned  = d['is_banned'] || false;

    const rblxLogo = `<svg viewBox="0 0 24 24" fill="#fff" width="18" height="18" aria-hidden="true"><path fill-rule="evenodd" d="M12 1L23 12L12 23L1 12ZM12 8L16 12L12 16L8 12Z"/></svg>`;

    parts.push(`<div>
      <div class="rblx-intel-card">
        <div class="rblx-header">
          <div class="rblx-icon-wrap">${rblxLogo}</div>
          <span class="rblx-platform-name">ROBLOX</span>
          <span class="rblx-intel-badge">GAMING INTEL</span>
        </div>
        <div class="rblx-body">
          <div class="rblx-avatar-col">
            ${rAvatar
              ? `<img class="rblx-avatar" src="${rAvatar}" alt="avatar" data-fallback="true">`
              : `<div class="rblx-avatar-fallback">⬛</div>`}
            ${rBanned ? `<span class="rblx-banned-chip">BANNED</span>` : ''}
          </div>
          <div class="rblx-data-col">
            <div>
              <div class="rblx-display-name">${esc(rDisplay)}</div>
              <div class="rblx-username">@${esc(rName)}</div>
            </div>
            <div class="rblx-facts">
              ${rId ? `<div class="rblx-fact"><span class="rblx-fact-label">USER ID</span><span class="rblx-fact-val">${esc(String(rId))}</span></div>` : ''}
              ${rJoined ? `<div class="rblx-fact"><span class="rblx-fact-label">JOINED</span><span class="rblx-fact-val">${esc(rJoined)}</span></div>` : ''}
              ${rDiscord ? `<div class="rblx-fact"><span class="rblx-fact-label">DISCORD</span><span class="rblx-fact-val" style="color:#7289da">${esc(rDiscord)}</span></div>` : ''}
            </div>
          </div>
        </div>
        <div class="rblx-history-section">
          <div class="rblx-section-label">USERNAME HISTORY</div>
          <div class="rblx-pills">
            ${rOldArr.length
              ? rOldArr.map(u => `<span class="rblx-pill">${esc(u)}</span>`).join('')
              : `<span class="rblx-pill rblx-pill-none">None</span>`}
          </div>
        </div>
        ${rId ? `<div class="rblx-footer">
          <a class="rblx-view-link" href="https://www.roblox.com/users/${esc(String(rId))}/profile"
             target="_blank" rel="noopener">
            ↗ View Profile on Roblox
          </a>
        </div>` : ''}
      </div>
    </div>`);
  }

  // GHunt (Google Account)
  const ghunt = currentResult.extras.ghunt;
  if (ghunt) {
    if (!ghunt.ok || ghunt.error) {
      parts.push(`<div>
        <div class="section-label" style="margin-bottom:8px">Google Account (GHunt)</div>
        <div style="background:var(--amber-lo);border:1px solid rgba(245,166,35,.2);border-radius:6px;padding:10px 14px;font-family:var(--mono);font-size:.76rem;color:var(--amber)">
          ⚠ ${esc(ghunt.error || 'GHunt lookup failed — upstream API may be unavailable.')}
        </div>
      </div>`);
    } else {
      const d = ghunt.data || {};
      const profile = d.data?.profile || d.profile || {};
      const gaia_id = profile['Gaia ID'] || d.gaia_id || '';
      const name    = profile['Name']    || d.name    || '';
      const pic     = profile['Profile Picture'] || d.profile_pic || '';
      const last_edit = profile['Last Update'] || d.last_update || '';
      const reviews_url = d.data?.maps_reviews || d.maps_reviews || '';
      const photos_url  = d.data?.photos_url   || d.photos_url  || '';
      const safePic = sanitizeImageUrl(pic);
      const safeReviewsUrl = sanitizeImageUrl(reviews_url);
      const safePhotosUrl = sanitizeImageUrl(photos_url);
      parts.push(`<div>
        <div class="section-label" style="margin-bottom:10px">Google Account (GHunt)</div>
        <div class="gaming-card" style="display:flex;gap:14px;align-items:flex-start">
          ${safePic ? `<img src="${safePic}" alt="Google avatar"
            style="width:56px;height:56px;border-radius:50%;border:2px solid var(--line2);flex-shrink:0"
            data-fallback="true">` : ''}
          <div style="flex:1">
            <div style="font-weight:700;font-size:.92rem;color:var(--text);margin-bottom:4px">${esc(name||'Unknown')}</div>
            ${gaia_id ? `<div style="font-family:var(--mono);font-size:.72rem;color:var(--text3)">Gaia ID: <span style="color:var(--amber)">${esc(gaia_id)}</span></div>` : ''}
            ${last_edit ? `<div style="font-family:var(--mono);font-size:.68rem;color:var(--text3);margin-top:4px">Last Update: ${esc(last_edit)}</div>` : ''}
            <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap">
              ${safeReviewsUrl ? `<a href="${safeReviewsUrl}" target="_blank" class="discord-view-btn" style="font-size:.7rem">📍 Maps Reviews ↗</a>` : ''}
              ${safePhotosUrl  ? `<a href="${safePhotosUrl}"  target="_blank" class="discord-view-btn" style="font-size:.7rem">📷 Photos ↗</a>`        : ''}
            </div>
          </div>
        </div>
      </div>`);
    }
  }

  // Victims (Compromised Machines)
  const victims = currentResult.extras.victims;
  if (victims) {
    if (!victims.ok || victims.error) {
      const noResults = victims.items?.length === 0;
      if (!noResults) {
        parts.push(`<div>
          <div class="section-label" style="margin-bottom:8px">Compromised Machines (Victims)</div>
          <div style="background:var(--green-lo);border:1px solid rgba(62,199,140,.2);border-radius:6px;padding:10px 14px;font-family:var(--mono);font-size:.76rem;color:var(--green)">
            ✓ No victim logs found for this target.
          </div>
        </div>`);
      }
    } else if (victims.items?.length) {
      parts.push(`<div>
        <div class="section-label" style="margin-bottom:4px">
          Compromised Machines (Victims)
          <span style="color:var(--red);margin-left:6px;font-family:var(--mono);font-size:.68rem">
            🚨 ${victims.total} machine${victims.total !== 1 ? 's' : ''} compromised
          </span>
        </div>
        <div style="background:var(--red-lo);border:1px solid rgba(232,64,64,.2);border-radius:6px;padding:8px 12px;font-family:var(--mono);font-size:.72rem;color:var(--red);margin-bottom:10px">
          ⚠ Stealer malware logs found. These machines had credentials harvested by malware.
        </div>
        <div id="victimsList">
          ${victims.items.map((v, i) => buildVictimCard(v, i)).join('')}
        </div>
        ${victims.has_more ? `
        <button class="load-more-btn" data-action="load-more-victims">
          ↓ Load more victims (${victims.total - victims.items.length} more)
        </button>` : ''}
      </div>`);
    }
  }

  // Discord → Roblox (Platform Connections)
  const d2r = currentResult.extras.discord_roblox;
  if (d2r?.ok && d2r.data) {
    const rd        = d2r.data;
    const rblxId    = rd.roblox_id || rd['User ID'] || '';
    const rblxName  = rd.name || rd.username || rd['Current Username'] || 'Unknown';
    const rblxDate  = (rd.created && rd.created !== 'N/A') ? rd.created.slice(0,10) : '';
    const rblxAvatar= sanitizeImageUrl(rd.avatar || rd['Avatar URL'] || '');

    // Get Discord side from previously received discord event
    const discEvt   = (currentResult.extras.discords || [])[0];
    const du        = discEvt?.user || null;
    const discName  = du ? (du.global_name || du.username || 'Unknown') : 'Unknown';
    const discHandle= du ? ('@' + (du.username || '─')) : '';
    const discId    = du?.id || '';
    const discDate  = du?.creation_date ? du.creation_date.slice(0,10) : '';
    const discAvatar= sanitizeImageUrl(du?.avatar_url || '');

    const robloxLogoSvg = `<svg viewBox="0 0 512 512" fill="currentColor" width="14" height="14" aria-hidden="true"><path d="M146.2 0L0 146.2l73.4 292.2L365.8 512 512 365.8 438.6 73.6zm98.1 290.8l-82.6-22.1 22.1-82.6 82.6 22.1z"/></svg>`;
    const discordLogoSvg = `<svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14" aria-hidden="true"><path d="${_SI.discord}"/></svg>`;

    parts.push(`<div>
      <div class="platform-card">
        <div class="platform-card-header">
          <div class="platform-card-icon">${discordLogoSvg}</div>
          <div class="platform-card-titles">
            <div class="platform-card-title">Platform Connections</div>
            <div class="platform-card-sub">Linked accounts across platforms</div>
          </div>
          <span class="platform-card-badge">1 link</span>
        </div>
        <div class="platform-bridge-row">
          <span class="platform-label-discord">${discordLogoSvg} Discord</span>
          <span class="platform-linked-center">
            <span class="platform-linked-dot"></span>
            Linked
            <span class="platform-linked-dot"></span>
          </span>
          <span class="platform-label-roblox">${robloxLogoSvg} Roblox</span>
        </div>
        <div class="platform-split">
          <div class="platform-col">
            ${discAvatar
              ? `<img class="platform-col-avatar" src="${discAvatar}" alt="Discord avatar" data-fallback="true">`
              + `<div class="platform-col-avatar-fallback" style="display:none">💬</div>`
              : `<div class="platform-col-avatar-fallback">💬</div>`}
            <div class="platform-col-name">${esc(discName)}</div>
            ${discHandle ? `<div class="platform-col-handle">${esc(discHandle)}</div>` : ''}
            ${discId ? `<span class="platform-col-id"># ${esc(discId)}</span>` : ''}
            ${discDate ? `<div class="platform-col-date">📅 ${esc(discDate)}</div>` : ''}
            ${discId ? `<a class="platform-col-link" href="https://discord.com/users/${esc(discId)}" target="_blank" rel="noopener">↗ View Profile</a>` : ''}
          </div>
          <div class="platform-divider"></div>
          <div class="platform-col">
            ${rblxAvatar
              ? `<img class="platform-col-avatar" src="${rblxAvatar}" alt="Roblox avatar" data-fallback="true">`
              + `<div class="platform-col-avatar-fallback" style="display:none">🟥</div>`
              : `<div class="platform-col-avatar-fallback">🟥</div>`}
            <div class="platform-col-name">${esc(rblxName)}</div>
            <div class="platform-col-handle">@${esc(rblxName)}</div>
            ${rblxId ? `<span class="platform-col-id"># ${esc(String(rblxId))}</span>` : ''}
            ${rblxDate ? `<div class="platform-col-date">📅 ${esc(rblxDate)}</div>` : ''}
            ${rblxId ? `<a class="platform-col-link" href="https://www.roblox.com/users/${esc(String(rblxId))}/profile" target="_blank" rel="noopener">↗ View Profile</a>` : ''}
          </div>
        </div>
      </div>
    </div>`);
  } else if (d2r && !d2r.ok) {
    const errMsg = d2r.error || 'Discord→Roblox lookup failed — no linked account found or API unavailable.';
    parts.push(`<div>
      <div class="section-label" style="font-size:.65rem;letter-spacing:.08em;text-transform:uppercase;color:var(--text3);margin-bottom:6px">Platform Connections</div>
      <div style="background:var(--amber-lo);border:1px solid rgba(245,166,35,.2);border-radius:6px;padding:8px 12px;font-family:var(--mono);font-size:.72rem;color:var(--amber)">⚠ ${esc(errMsg)}</div>
    </div>`);
  }

  el.innerHTML = parts.length
    ? parts.join('<hr style="border-color:var(--line);margin:14px 0">')
    : `<div style="color:var(--text3);font-family:var(--mono);font-size:.8rem">No network or gaming data.</div>`;

  // Attach error handlers to images with data-fallback (replaces inline onerror)
  el.querySelectorAll('img[data-fallback]').forEach(img => {
    img.addEventListener('error', function() {
      this.style.display = 'none';
      const sibling = this.nextElementSibling;
      if (sibling) sibling.style.display = 'flex';
    });
  });
}

// ══════════════════════════════════════════════════════
//  VICTIMS — File tree + viewer
// ══════════════════════════════════════════════════════
function buildVictimCard(v, idx) {
  const logId   = v.log_id || '';
  const users   = (v.device_users || []).slice(0,3).map(u => esc(u)).join(', ');
  const ips     = (v.device_ips   || []).slice(0,2).map(u => esc(u)).join(', ');
  const emails  = (v.device_emails|| []).slice(0,2).map(u => esc(u)).join(', ');
  const discs   = (v.discord_ids  || []).slice(0,2).map(u => esc(u)).join(', ');
  const hwids   = (v.hwids        || []).slice(0,1).map(u => esc(u)).join(', ');
  const docs    = v.total_docs || 0;
  const pwned   = (v.pwned_at  || '').slice(0,10);

  return `<div class="victim-card" id="victim-card-${idx}">
    <div class="victim-card-header" data-action="toggle-victim-tree" data-logid="${esc(logId)}" data-idx="${idx}">
      <div class="victim-card-left">
        <div class="victim-log-id">
          🚨 <span>${esc(logId)}</span>
          <button class="victim-expand-btn" data-action="toggle-victim-tree" data-logid="${esc(logId)}" data-idx="${idx}">
            Browse Files ▾
          </button>
        </div>
        <div class="victim-meta-grid">
          ${users ? `<span class="victim-meta-chip highlight">👤 ${users}</span>` : ''}
          ${ips   ? `<span class="victim-meta-chip">🌐 ${ips}</span>` : ''}
          ${emails? `<span class="victim-meta-chip">📧 ${emails}</span>` : ''}
          ${discs ? `<span class="victim-meta-chip">💬 ${discs}</span>` : ''}
          ${hwids ? `<span class="victim-meta-chip">🔑 ${hwids}</span>` : ''}
          ${pwned ? `<span class="victim-meta-chip">📅 ${esc(pwned)}</span>` : ''}
        </div>
      </div>
      <div class="victim-docs-count">
        <span>${docs.toLocaleString()}</span>
        <span class="victim-docs-label">files</span>
      </div>
    </div>
    <div class="victim-file-tree hidden" id="victim-tree-${idx}">
      <div class="text-dim-mono">Loading file tree…</div>
    </div>
  </div>`;
}

async function toggleVictimTree(logId, idx) {
  const treeEl = document.getElementById(`victim-tree-${idx}`);
  if (!treeEl) return;

  const isOpen = !treeEl.classList.contains('hidden');
  if (isOpen) {
    treeEl.classList.add('hidden');
    return;
  }

  treeEl.classList.remove('hidden');

  // Already loaded
  if (openVictimTrees[logId]) {
    treeEl.innerHTML = renderTree(openVictimTrees[logId].victim_tree, logId, 0);
    return;
  }

  // Fetch manifest
  treeEl.innerHTML = '<div style="font-family:var(--mono);font-size:.74rem;color:var(--text3)">⏳ Loading file tree…</div>';
  try {
    const r = await apiFetch(`/api/victims/${encodeURIComponent(logId)}/manifest`);
    if (!r.ok) {
      const err = await r.json();
      treeEl.innerHTML = `<div style="color:var(--red);font-family:var(--mono);font-size:.74rem">✗ ${esc(err.detail||'Failed')}</div>`;
      return;
    }
    const data = await r.json();
    openVictimTrees[logId] = data;
    treeEl.innerHTML = renderTree(data.victim_tree, logId, 0);
  } catch(e) {
    treeEl.innerHTML = `<div style="color:var(--red);font-family:var(--mono);font-size:.74rem">✗ ${esc(e.message)}</div>`;
  }
}

function renderTree(node, logId, depth) {
  if (!node) return '';
  if (node.type === 'file') {
    const size = formatBytes(node.size_bytes || 0);
    return `<div class="tree-node">
      <div class="tree-file">
        <span class="text-dim" aria-hidden="true">📄</span>
        <span class="tree-file-name" title="${esc(node.name)}">${esc(node.name)}</span>
        <span class="tree-file-size">${size}</span>
        <button class="tree-file-btn"
          data-action="view-victim-file" data-logid="${esc(logId)}" data-fileid="${esc(node.id)}" data-name="${esc(node.name)}">
          View
        </button>
      </div>
    </div>`;
  }

  // Directory
  const nodeId   = `tree-${logId}-${node.id}`.replace(/[^a-zA-Z0-9-_]/g,'_');
  const children = (node.children || []).sort((a,b) => {
    // dirs first, then files, alphabetical
    if (a.type !== b.type) return a.type === 'directory' ? -1 : 1;
    return (a.name||'').localeCompare(b.name||'');
  });

  if (!children.length) return '';

  return `<div class="tree-node">
    <div class="tree-dir" data-action="toggle-tree-dir" data-nodeid="${nodeId}">
      <span class="tree-dir-icon" id="icon-${nodeId}">▶</span>
      <span>📁 ${esc(node.name || '/')}</span>
      <span class="tree-dir-count">(${children.length})</span>
    </div>
    <div class="tree-children hidden" id="${nodeId}">
      ${children.map(c => renderTree(c, logId, depth+1)).join('')}
    </div>
  </div>`;
}

function toggleTreeDir(nodeId) {
  const el   = document.getElementById(nodeId);
  const icon = document.getElementById(`icon-${nodeId}`);
  if (!el) return;
  const isOpen = !el.classList.contains('hidden');
  el.classList.toggle('hidden', isOpen);
  if (icon) icon.textContent = isOpen ? '▶' : '▼';
}

async function viewVictimFile(logId, fileId, fileName) {
  const overlay  = document.getElementById('fileViewerOverlay');
  const titleEl  = document.getElementById('fileViewerTitle');
  const contentEl= document.getElementById('fileViewerContent');
  const metaEl   = document.getElementById('fileViewerMeta');

  titleEl.textContent   = fileName;
  contentEl.textContent = '⏳ Loading…';
  metaEl.textContent    = '';
  overlay.classList.add('visible');

  try {
    const r = await apiFetch(
      `/api/victims/${encodeURIComponent(logId)}/files/${encodeURIComponent(fileId)}`
    );
    if (!r.ok) {
      const err = await r.json().catch(() => ({detail:'Failed'}));
      contentEl.textContent = `✗ Error: ${err.detail||'File not found'}`;
      return;
    }
    const text = await r.text();
    contentEl.textContent = text || '(empty file)';
    metaEl.textContent    = `${text.split('\n').length} lines · ${formatBytes(text.length)}`;
  } catch(e) {
    contentEl.textContent = `✗ ${e.message}`;
  }
}

function closeFileViewer() {
  document.getElementById('fileViewerOverlay').classList.remove('visible');
}

function copyFileContent() {
  const text = document.getElementById('fileViewerContent').textContent;
  writeClipboard(text);
  showToast('File content copied');
}

async function loadMoreVictims() {
  const v = currentResult.extras.victims;
  if (!v?.next_cursor) return;
  const q = currentResult.query;
  try {
    const r = await apiFetch(`/api/victims/search?q=${encodeURIComponent(q)}&cursor=${encodeURIComponent(v.next_cursor)}&page_size=10`);
    const data = await r.json();
    const newItems = data.items || [];
    v.items        = [...v.items, ...newItems];
    v.next_cursor  = data.next_cursor || '';
    v.has_more     = data.meta?.has_more || false;
    // Re-render victims list
    const list = document.getElementById('victimsList');
    if (list) {
      const startIdx = v.items.length - newItems.length;
      list.innerHTML += newItems.map((vi, i) => buildVictimCard(vi, startIdx + i)).join('');
    }
  } catch(e) {
    showToast('Failed to load more victims', true);
  }
}

// Close file viewer on Escape
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeFileViewer();
});
