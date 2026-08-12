// * breadcrumb.js
(function() {
	if (window.matchMedia("(min-width: 1150px)").matches) {
		$(".breadcrumbs_dropdown .breadcrumbs__item")
			.not(":first")
			.hover(function(e) {
				$(this).toggleClass("show");
			});
	}

	if (window.matchMedia("(max-width: 1149px)").matches) {
		$(".breadcrumbs_dropdown .breadcrumbs__btn").click(function() {
			$(this)
				.closest(".breadcrumbs__item")
				.toggleClass("show");

			$(document).bind("click.wrapper", function(e) {
				if ($(e.target).closest(".breadcrumbs__item").length == 0) {
					$(".breadcrumbs__item").removeClass("show");
					$(document).unbind("click.wrapper");
				}
			});
		});
	}
})();

// * general.js
$(function() {
	// $(".rev-form__f-dd").each(function(){
	// 	if($(this).is(':empty')) {
	// 		$(this).remove();
	// 	}
	// });
});
// Появлении системной сообшении при ошибке
(function() {
	if ($(".system-message").length) {
		setTimeout(function() {
			$(".system-message").addClass("is-show");
		}, 2000);
	}
})();

//Быстрый поиск на странице Бренд
(function() {
	var lists = document.querySelectorAll(".list-wrapper");

	Array.prototype.forEach.call(lists, function(el, index) {
		el.setAttribute("id", "list-" + index);

		var id = el.id;

		var options = {
			valueNames: ["name"]
		};

		var list = new List(id + "", options);

		$(".search").keyup(function() {
			list.search($(this).val());

			if (list.matchingItems.length === 0) {
				$("#" + id).hide();
			} else {
				$("#" + id).show();
			}
		});
	});
})();

// Скопировать текст на буфер
(function() {
	const span = document.querySelector(".order-info__track-num");
	if (span) {
		document.querySelector(".order-info__copy-track").addEventListener("click", copy_password);
	}

	function copy_password(e) {
		e.preventDefault();
		var copyText = document.querySelector(".order-info__track-num");
		var textArea = document.createElement("textarea");
		textArea.value = copyText.textContent;
		document.body.appendChild(textArea);
		textArea.select();
		document.execCommand("Copy");
		textArea.remove();
	}
})();

//Scroll to the top of block when clicking on the tab menu items on Items page
$(".item-tabs__list_js a").on("click", function(e) {
	e.preventDefault();
	$("html,body").animate(
		{
			scrollTop: $("#item-tabs").offset().top - 50
		},
		300
	);
});

//LazyLoad

(function() {
	lazyLoadInstance = new LazyLoad({
		elements_selector: ".lazy-img"
		// ... more custom settings?
	});
})();

//Initialization of tippy

if (typeof tippy === "function") {
	tippy(document.querySelectorAll(".tippy"), {
		delay: 100
	});
}
// tippy() && ;

$(".show-toggle-btn").on("click", function(e) {
	e.preventDefault();
	$(".outer-wrapper").toggleClass("show-mode");
});

// Script for making universal "clock to show dropdown" * dropdowns.js
var Dropdowns = {
	ShowHide: function(options) {
		this.dropWrapper = options.dropWrapper;
		this.dropTrigger = options.dropTrigger;
		this.activeClass = options.activeClass;
		this.stopPropEl = options.stopPropEl;
		this.showMethod = options.showMethod;

		var context = this;

		this.show = function() {
			//if onclick
			if (this.showMethod === "click") {
				$(this.dropWrapper).on("click", this.dropTrigger, function(e) {
					e.preventDefault();
					$(context.dropWrapper).each(function() {
						$(this).removeClass(context.activeClass);
					});

					$(this)
						.closest(context.dropWrapper)
						.toggleClass(context.activeClass);

					$(document).bind("click.wrapper", function(e) {
						if ($(e.target).closest(context.dropTrigger).length == 0) {
							$(context.dropWrapper).removeClass(context.activeClass);
							$(document).unbind("click.wrapper");
						}
					});
				});
			}
			//if onhover
			if (this.showMethod === "hover") {
				$(this.dropTrigger).hover(function() {
					$(this)
						.closest(context.dropWrapper)
						.toggleClass(context.activeClass);
				});
			}
		};

		this.stopProp = function() {
			$(this.dropWrapper).on("click", this.stopPropEl, function(e) {
				e.stopPropagation();
			});
		};

		this.init = function() {
			this.show();
			this.stopProp();
		};

		this.init();
	}
};

//Top-menu
(function() {
	var topMenu = new Dropdowns.ShowHide({
		dropWrapper: ".top-menu_js",
		dropTrigger: ".top-menu__btn-toggler",
		activeClass: "menu-open",
		stopPropEl: ".top-menu__sec-menu-list li a",
		showMethod: "hover"
	});
})();

//
(function() {
	var drops = new Dropdowns.ShowHide({
		dropWrapper: ".dropdowns",
		dropTrigger: ".drophead",
		activeClass: "is-active",
		stopPropEl: ".dropdowns label",
		showMethod: "click"
	});

	$(".dropdowns").on("click", "label", function(e) {
		e.stopPropagation();
	});

	$(".dropdowns").on("change", "label", function(e) {
		$(this)
			.closest(".drop-list__item")
			.toggleClass("is-checked");
	});
})();

//stars-rating stars * rating.js
(function() {
  var starClicked = false;

  $(function() {
    $(".rate-it__star_js").click(function() {
      $(this)
        .children(".selected")
        .addClass("is-animated");
      $(this)
        .children(".selected")
        .addClass("pulse");

      var target = this;

      setTimeout(function() {
        $(target)
          .children(".selected")
          .removeClass("is-animated");
        $(target)
          .children(".selected")
          .removeClass("pulse");
      }, 1000);

      starClicked = true;
    });

    $(".full").click(function() {
      if (starClicked == true) {
        setFullStarState(this);
      }

      var $this = $(this);

      $this.closest(".rate-it").data("vote", $this.data("value"));
    });

    $(".full").hover(function() {
      if (starClicked == false) {
        setFullStarState(this);
      }
    });
  });

  function updateStarState(target) {
    $(target)
      .parent()
      .prevAll()
      .addClass("animate");
    $(target)
      .parent()
      .prevAll()
      .find(".full")
      .addClass("star-colour");

    $(target)
      .parent()
      .nextAll()
      .removeClass("animate");
    $(target)
      .parent()
      .nextAll()
      .find(".full")
      .removeClass("star-colour");
  }

  function setFullStarState(target) {
    $(target).addClass("star-colour");
    $(target)
      .parent()
      .addClass("animate");

    updateStarState(target);
  }

  /* Reseting rating inputs
	=================================*/

  $(".rate-it__clear").on("click", function(e) {
    e.preventDefault();
    var $this = $(this);

    $(".full")
      .add(".rate-it__star_js")
      .removeClass("animate star-colour");
  });
})();

//Submit form with ctrl+enter * form-submit.js
(function() {
  $(".rev-form__form").on("keydown", function(e) {
    if (e.keyCode == 13 && e.ctrlKey)
      $(this)
        .closest("form")
        .submit();
  });
})();

//Toggling dropdowns * review-toggle-sign-in.js
(function() {
	$(".form-l").on("click", ".rev-form__descr a", function(e) {
		e.preventDefault();

		$(this)
			.closest(".rev-form__top")
			.siblings(".rev-form__sign-in")
			.slideToggle();
	});

	$(".form-l").on("click", ".rev-form__sign-in-close", function(e) {
		e.preventDefault();

		$(this)
			.closest(".rev-form__sign-in")
			.slideToggle();
	});
})();

//* button-anim.js
(function() {
	$(".btn_spread")
		.on("mouseenter", function(e) {
			var parentOffset = $(this).offset(),
				relX = e.pageX - parentOffset.left,
				relY = e.pageY - parentOffset.top;
			$(this)
				.find(".hover-anim")
				.css({ top: relY, left: relX });
		})
		.on("mouseout", function(e) {
			var parentOffset = $(this).offset(),
				relX = e.pageX - parentOffset.left,
				relY = e.pageY - parentOffset.top;
			$(this)
				.find(".hover-anim")
				.css({ top: relY, left: relX });
		});
})();

// Tippy || tooltips * tooltips.js
(function() {
	var tooltips = document.querySelectorAll(".has-tooltip");

	var tooltipText;

	Array.prototype.forEach.call(tooltips, function(tooltip) {
		if (tooltip.classList.contains("active") && !tooltip.classList.contains("pd-color")) {
			tooltipText = tooltip.getAttribute("data-active");
		} else {
			tooltipText = tooltip.getAttribute("data-title");
		}

		if (!tooltip.classList.contains("is-init")) {
			tooltip.classList.add("is-init");

			tooltipSpan = document.createElement("span");

			tooltipSpan.className = "b-tooltip";
			tooltipSpan.innerHTML = tooltipText;
			tooltip.appendChild(tooltipSpan);
		} else {
			return;
		}
	});

	// $(".outer-wrapper").on("click", ".item-act-btn", function(e) {
	// 	var $this = $(this),
	// 		dataTitle = $this.data("title"),
	// 		dataActiveTitle = $this.data("active"),
	// 		bTooltip = $this.find(".b-tooltip");

	// 	$this.toggleClass("active");

	// 	if ($this.hasClass("active")) {
	// 		bTooltip.text(dataActiveTitle);
	// 	} else {
	// 		bTooltip.text(dataTitle);
	// 	}
	// });
})();

// * priojs.js
$(function() {
  if ($(".top-menu").length) {
    new PrioMenu({
      toggler: ".top-menu__btn-toggler",
      mainMenuWrapper: ".top-menu",
      secMenuWrapper: ".top-menu__sec-menu",
      mainMenu: ".top-menu__list",
      secMenu: ".top-menu__sec-menu-list",
      openMenuClass: "menu--open",
      mainItems: ".top-menu__list > li",
      secItems: ".top-menu__sec-menu-list > li",
      parentBlock: ".site-header__top-menu"
      // buttonText: ''
    });
  }
});

//Desktop vertical menu * verticalMenu.js
(function() {
	$(document).ready(function() {
		var nCurPosX; // текущее положение курсора

		$("html").mousemove(function(e) {
			if (!e) e = window.event;
			nCurPosX = e.clientX;
		});

		$(".vert-m__item_has-submenu").hover(
			function() {
				var $curItem = $(this),
					$submenu = $curItem.find(".vert-m__submenu-book");

				$curItem.addClass("hover");

				/*
			делаем задержку чтобы при случайном наведении на пункт под меню не показывалось
		*/
				setTimeout(function() {
					/* если по истечению задержки мы все еще на том же пункт меню,
				значит показываем подменю
			*/

					if ($curItem.hasClass("hover")) {
						$submenu.css("display", "block");
					}
				}, 100);
			},
			function() {
				var nPosXStart = nCurPosX,
					$submenu = $(this).find(".vert-m__submenu-book"),
					$curItem = $(this);

				$curItem.removeClass("hover");
				/*
			делаем небольшую задержку чтобы определить направление движение курсора
		*/
				setTimeout(function() {
					var nPosXEnd = nCurPosX;

					// если в сторону подменю, значит делаем большую задержку для возможности движения по диагонали
					if (nPosXEnd - nPosXStart > 0)
						setTimeout(function() {
							/*
						если по истечению задержки курсор находится на подменю или текущем пункте меню
						тогда не прячем подменю
					*/
							if (!$submenu.hasClass("hover") && !$curItem.hasClass("hover")) {
								$submenu.css("display", "none").removeClass("hover");
							}
						}, 300);
					// если нет и мы ушли с текущего пункта меню, моментально скрываем подменю
					else if (!$submenu.hasClass("hover") && !$curItem.hasClass("hover")) {
						$submenu.css("display", "none").removeClass("hover");
					}
				}, 10);
			}
		);

		$(".vert-m__submenu-book").hover(
			function() {
				$(this).addClass("hover");
			},
			function() {
				$(this).removeClass("hover");
			}
		);
	});
})(); //iefe

// * easymenu.js
$(".multimenu").easymenu();
$(".vert-m_js .vert-m__list").easymenu({
  menu_class: ".vert-m__list"
});

// Скрипт "Показать еще категории в Мега меню" * categ-menu__toggle-qty.js
(function() {
	var showMoreItems = {
		container: $(".menu-categ__list_show-more"),
		moreText: $(".menu-categ__list_show-more").data("more-text"),

		init: function() {
			this.initialShow();
		},

		initialShow: function() {
			this.container.each(function(i, v) {
				var $v = $(v),
					x = parseInt($v.data("show")),
					liCount = parseInt($v.find("li").size());

				$v.find("li:lt(" + x + ")").show();

				if (liCount > x) {
					$("<a></a>", {
						text: showMoreItems.moreText,
						href: "#"
					})
						.addClass("menu-categ__toggle-qty")
						.insertAfter($v)
						.on("click", showMoreItems.toggleItemsQty);
				}
			});
		},

		toggleItemsQty: function(e) {
			e.preventDefault();
			e.stopPropagation();
			var $this = $(this),
				container = $this.prev(showMoreItems.container);

			//Покажем все
			if (!$this.hasClass("is-shows-all")) {
				var x = parseInt(container.find("li").size());

				container.find("li:lt(" + x + ")").fadeIn();
				$this.addClass("is-shows-all");
				// setTimeout(function(){
				$this.html(container.data("less-text"));
				// },300);
			} else {
				//Вернем как было
				x = parseInt(container.data("show") - 1);

				container.find("li:gt(" + x + ")").fadeOut();
				$this.removeClass("is-shows-all");
				// setTimeout(function(){
				$this.html(container.data("more-text"));
				// },300);
			}
		}
	};
	showMoreItems.init();
})();

// * header-elements.js
$(function() {
	$(".cat-menu-btn-desk:not(.on-sidebar)").on("click", function(e) {
		e.preventDefault();
		var $this = $(this);
		$this.closest(".site-header__cat-btn").toggleClass("active");
		$("body").toggleClass("is-overlayed");

		$(document).bind("click.wrapper", function(e) {
			if ($(e.target).closest($this).length == 0) {
				$("body").removeClass("is-overlayed");
				$(".site-header__cat-btn").removeClass("active");
				$(document).unbind("click.wrapper");
			}
		});
	});
	$(".mega-m").on(
		"click",
		function(e) {
			e.stopPropagation();
		},
		true
	);

	var cityChooseBtns = $(".city-choose-drop__btns .btn");

	cityChooseBtns.on("click", function(e) {
		$(this)
			.closest(".city-chooser")
			.removeClass("is-active");
		$(this)
			.closest(".def-list")
			.removeClass("is-active");
		$(this)
			.closest(".univ-dropd")
			.remove();
	});

	//Динамически выдвинуть влево меню
	if ($(".hor-menu__item.vertikal").length) {
		var catBtn = $(".hor-menu__item.has-subm.vertikal"),
			leftPos = catBtn && catBtn.position().left;

		catBtn.find(".hor-menu__submenu").css("left", leftPos + "px");
	}

	//Динамически выдвинуть влево меню
	if ($(".site-header__mid_btn-in-mid").length) {
		var catBtn = $(".site-header__mid_btn-in-mid .site-header__cat-btn"),
			leftPos = catBtn && catBtn.position().left;

		catBtn.find(".site-header__nav").css("left", -leftPos + "px");
	}

	//Показываем overlay с задержкой чтобы случайно не показывать.
	$(".no-touch .has-subm:not(.hor-menu__item_table)").hoverDelay({
		over: function(e) {
			$("body").addClass("is-overlayed");
		},
		out: function(e) {
			$("body").removeClass("is-overlayed");
		},
		delayOver: 100,
		delayOut: 0
	});

	//Hover у меню в вариантлах 5-2 и 6-2

	$(".no-touch .hor-menu__item_table").hoverDelay({
		over: function(e) {
			$("body").addClass("is-overlayed");
			var $this = $(this),
				items = $this.siblings();

			items.removeClass("active");
			$this.addClass("active");
		},
		out: function(e) {
			var $this = $(this),
				items = $this.siblings(),
				firstItem = $(".hor-menu__item_table:first-child");

			$this.removeClass("active");

			if (!items.hasClass("active")) {
				firstItem.addClass("active");
			}

			$("body").removeClass("is-overlayed");
		},
		delayOver: 100,
		delayOut: 0
	});
});

/*
	Horizontal menu priority script * hor-menu-flexmenu.js
*/
// $(function() {
// document.addEventListener("DOMContentLoaded", function(){
// window.onload = function(){
// });
(function() {
	if ($(".hor-menu_buttoned").length) {
		new PrioMenu({
			toggler: ".hor-menu__btn-toggler",
			mainMenuWrapper: ".hor-menu_buttoned",
			secMenuWrapper: ".hor-menu__sec-menu",
			mainMenu: ".hor-menu__list",
			secMenu: ".hor-menu__sec-menu-list",
			openMenuClass: "menu--open",
			mainItems: ".hor-menu__list > li",
			secItems: ".hor-menu__sec-menu-list > li",
			parentBlock: ".hor-menu_buttoned"
			// buttonText: ''
		});

		$(".hor-menu__sec-menu-list > .hor-menu__item").each(function(i, v) {
			$(v).removeClass("has-subm");
		});
	}

	//Initialize flexmenu of horizontal menu in Header 5

	$(".hor-menu_table .hor-menu__list").flexMenu({
		linkText: "...",
		popupClass: "menu-univ-popup univ-dropd",
		cutoff: 0,
		linkTitle: ""
	});

	var tableItems = $(".hor-menu_table .flexMenu-viewMore");
	if (tableItems.length) {
		tableItems.find(".hor-menu__item").each(function() {
			$(this)
				.addClass("moved-item")
				.removeClass("has-subm");
			tableItems.closest(".hor-menu_table").addClass("loaded");
		});

		$(".touch .flexMenu-viewMore").on(
			"click",
			function() {
				e.stopPropagation();
			},
			true
		);
	}

	//Initialize flexmenu of horizontal menu in Header 5
	$(".page-menu .page-menu__list").flexMenu({
		linkText: "...",
		popupClass: "menu-univ-popup univ-dropd",
		linkTitle: ""
	});

	var tableItems = $(".page-menu .flexMenu-viewMore");
	if (tableItems.length) {
		tableItems.find(".page-menu__item").each(function() {
			$(this)
				.addClass("moved-item")
				.removeClass("has-subm");
		});
		tableItems.closest(".page-menu").addClass("loaded");
	}
	// var allItemsLength = 0;
	// $(".page-menu__item").each(function(){

	// });

	//Добавис класс 'loaded' когда нет "еще" меню чтобы у меню и пунктов форм-ся высота
	$(".site-header_15 .hor-menu__list > li").each(function() {
		var $this = $(this);

		if (!$this.hasClass(".flexMenu-viewMore")) {
			$this.closest(".hor-menu").addClass("loaded");
		}
	});
	//Чтобы добавить эффект затемнение при ховере
	$(".flexMenu-viewMore").addClass("has-subm");

	//Чтобы добавить эффект затемнение при ховере
	$(".flexMenu-viewMore .moved-item").removeClass("hor-menu__item_table");

	$(".site-header").on("mouseenter mouseleave", ".flexMenu-viewMore.has-subm", function() {
		setTimeout(function() {
			$("body").toggleClass("is-overlayed");
		}, 100);
	});

	//Потому что в css изначально overflow:hidden чтобы скрыть пункты меню до иниц. flexmenu
	$(".page-menu, .hor-menu_table").css("overflow", "visible");

	// К правку "Главный меню обрезается . "
	$(window).load(function() {
		var megaMenu = $(".mega-m");
		var menuHeight = megaMenu.innerHeight();
		var pageHeight = $(document).innerHeight();
		var menuBarHeight = $(".site-header__menu-row").innerHeight();
		var menuBarTopOffset = $(".site-header__menu-row").length && $(".site-header__menu-row").offset().top;

		var spaceFromMenuToBottom = pageHeight - menuHeight - menuBarHeight - menuBarTopOffset;

		if (spaceFromMenuToBottom < 0) {
			var absOffset = Math.abs(spaceFromMenuToBottom); //making it posituve number
			var averageHeight = menuHeight * 0.9 - absOffset;
			megaMenu.addClass("is-fixed");
			megaMenu.css({
				height: averageHeight + "px",
				overflowX: "hidden",
				overflowY: "auto"
			});
		}
	});
})();

/*
	Adaptive Menu settings and scripts * adaptive-menu.js
*/

jQuery(document).ready(function($) {
	var mmenu = $("#mmenu");
	if (mmenu.length) {
		mmenu.mmenu(
			{
				extensions: ["pagedim-black", "fullscreen"],
				navbar: {
					// "title": ''
				}
			},
			{
				// panelNodetype: ["ul", "ol"],
				classNames: {
					selected: "active"
				},
				language: "ru",
				offCanvas: {
					page: {
						nodetype: "main"
						// selector: "body > #my-page"
					}
				}
				// openingInterval: 0
			}
		);
	}

	var API = mmenu.data("mmenu");
	//Adding close button dynamically
	(function() {
		var btnClose = '<a class="mobile-nav__close" href="/work"></a>';

		mmenu.find(".mm-navbar").append(btnClose);
		lazyLoadInstance.update();
		if (mmenu.length) {
			API.initPanels(mmenu);
		}
	})();

	//Closing menu with X button
	$(".mobile-nav").on("click", ".mobile-nav__close", function() {
		API.close();
		//Script below in necessary for resetting mobile menu to initial state
		setTimeout(function() {
			if ($(".mm-panels .mm-panel:not(first-child)").hasClass("mm-panel_opened")) {
				$(".mm-panels .mm-panel:not(first-child)").removeClass("mm-panel_opened");
				$(".mm-panels .mm-panel:not(first-child)").addClass("mm-hidden");
				$(".mm-panels .mm-panel:first-child").addClass("mm-panel_opened");
				$(".mm-panels .mm-panel:first-child").removeClass("mm-panel_opened-parent");
				$(".mm-panels .mm-panel:first-child").removeClass("mm-hidden");
			}
			//Return button visibility if it's hidden when we open catalog from catalog button
			$("#mm-1 .mm-btn_prev").css("visibility", "visible");
		}, 300);
		return false;
	});

	//Opening catalog right from catalog button pn the page
	$(".site-header").on("click", ".cat-menu-btn-mob", function() {
		API.open();
		$(".mobile-nav__item_catalog .mm-btn").trigger("click");
		$("#mm-1 .mm-btn_prev").css("visibility", "hidden");
		return false;
	});

	(function() {
		//Move mobile search form into mobile sidebar
		$(".site-header > .mob-search:first").appendTo(".mobile-nav__item_search");

		//Change Catalog text to remove items quantity
		var catText = $(".mm-panel:first-child")
			.find(".mobile-nav__item:first-child .mobile-nav__text")
			.text();
		$(".mm-panel:nth-child(2) .mm-navbar__title").text(catText);

		//Removing text from navbar
		$(".mobile-nav").on("click", ".mobile-nav__item", function(e) {
			var $this = $(this),
				menuItem = $this.closest(".mobile-nav__item");

			if (menuItem.hasClass("mobile-nav__item_callback")) {
				setTimeout(function() {
					if ($(".mm-panel").hasClass("mm-panel_opened")) {
						$(".mm-panel_opened .mm-navbar__title").remove();
						$(".mm-panel_opened")
							.find(".mobile-nav__item ")
							.addClass("removeBorder");
					}
				}, 100);
			}
		});
	})();
});

$(".menu-toggle-text__icon").on("click", function() {
	$(this)
		.closest(".mobile-nav__btn_expand")
		.toggleClass("active");

	$(".mob-side-dropmenu").slideToggle();
});

//Mobile footer * footer-elements.js
$(function() {
  if (window.matchMedia("(max-width: 767px)").matches) {
    $(".site-footer").on("click", ".f-info__header", function() {
      var $this = $(this),
        $allHeaders = $(".f-info__header"),
        $thisBody = $this.next(".f-info__body");

      if (!$thisBody.is(":visible")) {
        $allHeaders.removeClass("active");

        $(".site-footer")
          .find(".f-info__body")
          .slideUp();

        $thisBody.slideDown();
        $this.addClass("active");
      } else {
        $this.removeClass("active");
        $thisBody.slideUp();
      }
    });
  }

  //Scroll to top
  (function() {
    $(".site-footer__item_scroll-top").click(function() {
      $("html, body").animate({ scrollTop: 0 }, "fast");
    });
  })();
});

//Info page scripts * info-page.js
$(function() {
	//Creating menu for info page in tablet
	if (window.matchMedia("(max-width: 1249px)").matches) {
		$(".info-sdb__content")
			.clone()
			.appendTo(".info-pg__dropdown");
	}
	//show menu in tablet
	$(".info-pg__tab-menu-btn").on("click", function() {
		$(this)
			.closest(".info-pg__tab-menu")
			.toggleClass("active");

		$("#my-page").toggleClass("is-overlayed");

		$(document).bind("click.wrapper", function(e) {
			if ($(e.target).closest(".info-pg__top").length == 0) {
				$(".info-pg__tab-menu").removeClass("active");
				$("#my-page").removeClass("is-overlayed");
				$(document).unbind("click.wrapper");
			}
		});
	});
	//Show Menu in mobile info page
	if (window.matchMedia("(max-width: 767px)").matches) {
		$(".info-sdb__header_btn").on("click", function() {
			$(this)
				.closest(".info-sdb__wr_bd")
				.toggleClass("active");
			$("#my-page").toggleClass("is-overlayed");

			$(document).bind("click.wrapper", function(e) {
				if ($(e.target).closest(".info-sdb__wr_bd").length == 0) {
					$(".info-sdb__wr_bd").removeClass("active");
					$("#my-page").removeClass("is-overlayed");
					$(document).unbind("click.wrapper");
				}
			});
		});
	}

	//If there is no menu in info page we get rid of the button in tablet
	if ($(".info-pg__dropdown").is(":empty")) {
		$(".info-pg__tab-menu").remove();
	}

	//Sticking item to top in item page info link page
	var bottomOffset = $(".site-footer").height() + 50;
	$("#sticky-shop-item").sticky({
		topSpacing: 10,
		bottomSpacing: bottomOffset
	});

	//remove indentation of comments if there are more than 10 comments in one comment
	$(".comment.has-reply").each(function(i, v) {
		var comment = $(v);

		comment.find(".comment").each(function(i, v) {
			var $this = $(this);

			if (i > 9) {
				$this.removeClass("is-reply");
			}
		});
	});
});

//Reviews scripts * reviews.js
$(function() {
	if (window.matchMedia("(max-width: 1249px)").matches) {
		$(".reviews__main-info").prependTo(".reviews__header");
	}
});

//Sign page scripts *sign-page.js
$(function() {
	//Auth page dom manipulation
	(function() {
		$("<div></div>")
			.addClass("auth-links")
			.appendTo(".wa-login-form-actions");

		$(".wa-login-form-wrapper .wa-field-password .wa-login-forgotpassword-url")
			.add(".wa-login-form-actions .wa-signup-url")
			.appendTo(".auth-links");
	})();
});

//Account page scripts
//Beginning of * acount-page.js
$(function() {
	//Toggle views in Accout history page
	if (window.matchMedia("(max-width: 767px)").matches) {
		$(".mob-orders-view-toggle__tab").on("click", function() {
			var $this = $(this);

			$this.siblings().removeClass("active");
			$this.addClass("active");

			if ($this.hasClass("short")) {
				$(".order-list").addClass("order-list_short");
			} else {
				$(".order-list").removeClass("order-list_short");
			}
		});

		//Change text of mobile menu in accunt page
		if ($(".account-pg").find(".info-sdb__header_btn strong").length) {
			$(".account-pg")
				.find(".info-sdb__header_btn strong")
				.text($(".info-sdb__header_btn strong").data("mobile-text"));
		}
	}
});

//End of * acount-page.js

//FAQ * faq.js
(function() {
  $(".faq").on("click", ".faq__dd", function() {
    var $this = $(this),
      $currentDt = $this.next(".faq__dt"),
      $items = $this.closest(".faq__item").siblings(),
      $otherDt = $items.find(".faq__dt");

    if ($otherDt.is(":visible")) {
      $items.removeClass("active");
      $otherDt.slideUp();
    }
    $this.toggleClass("active");
    $currentDt.slideToggle();
  });
})();

//Checkout Tabs * checkout.js
(function() {
	$(".checkout-pg__main").on("click", ".checkout-pg__tabs-item", function(e) {
		var selfItem = $(this),
			index = selfItem.index();

		selfItem
			.addClass("active")
			.siblings()
			.removeClass("active");

		var tab = selfItem
			.closest(".checkout-pg__main")
			.find(".checkout-pg__tab-content")
			.eq(index);

		tab
			.fadeIn(150)
			.siblings(".checkout-pg__tab-content")
			.hide();
	});
})();

/* Checkout radio toggle
=================================*/
(function() {
	$(".check-brief__toggle, .check-brief__mobile-hide").on("click", function() {
		var $this = $(this);

		$(".check-brief__main").slideToggle(function() {
			$(".check-brief__toggle").toggleClass("active");
		});
	});
})();

/*---------Sliders * slider-inits.js
============================================*/

(function() {
	//Main slider

	if ($(".main-slider_js").length) {
		var mainSlider = new Swiper(".main-slider_js", {
			// autoHeight: true,
			speed: 1000,
			watchOverflow: true,
			navigation: {
				prevEl: ".main-slider__nav .slider-ar:first-child",
				nextEl: ".main-slider__nav .slider-ar:last-child"
			},
			pagination: {
				el: ".swiper-pagination",
				clickable: true
			},
			on: {
				init: function() {
					var img = $(".main-slider_js .main-slider__slide:nth-child(1) img");
					if (img.data("height")) {
						$(".main-slider_js")
							.css("height", img.data("height"))
							.trigger("balance_homeslider_image_loaded");
					} else {
						var src = img.data("src");
						$("<img>")
							.attr("src", src)
							.load(function() {
								img.attr("src", src);
								$(".main-slider_js")
									.trigger("balance_homeslider_image_loaded")
									.find(".swiper-slide-active .swiper-lazy-preloader")
									.remove();
								var scale = 1;
								if (this.width > img.parent().width()) {
									scale = this.width / img.parent().width();
								}
								$(".main-slider_js").css("height", this.height / scale);
								img.data("height", this.height / scale);
							})
							.each(function() {
								//ensure image load is fired. Fixes opera loading bug
								if (this.complete) {
									$(this).trigger("load");
								}
							});
					}
				},
				slideChange: function() {
					if (typeof _balance_homeslider_autoplay == "number") clearInterval(_balance_homeslider_autoplay);
					var img = $(".main-slider_js .main-slider__slide:nth-child(" + (mainSlider.activeIndex + 1) + ") img");
					if (img.data("height")) {
						$(".main-slider_js")
							.css("height", img.data("height"))
							.trigger("balance_homeslider_image_loaded");
					} else {
						var src = img.data("src");
						$("<img>")
							.attr("src", src)
							.load(function() {
								img.attr("src", src);
								$(".main-slider_js")
									.trigger("balance_homeslider_image_loaded")
									.find(".swiper-slide-active .swiper-lazy-preloader")
									.remove();
								var scale = 1;
								if (this.width > img.parent().width()) {
									scale = this.width / img.parent().width();
								}
								$(".main-slider_js").css("height", this.height / scale);
								img.data("height", this.height / scale);
							})
							.each(function() {
								//ensure image load is fired. Fixes opera loading bug
								if (this.complete) {
									$(this).trigger("load");
								}
							});
					}
				}
			}
		});
		if (parseInt($(".main-slider_js").data("auto")) > 0) {
			$(".main-slider_js").on("balance_homeslider_image_loaded", function() {
				// console.log("balance_homeslider_image_loaded");
				_balance_homeslider_autoplay = setInterval(function() {
					clearInterval(_balance_homeslider_autoplay);
					if (mainSlider.activeIndex + 1 == $(".main-slider_js .main-slider__slide").size()) {
						mainSlider.slideTo(0);
					} else {
						mainSlider.slideNext(1000);
					}
				}, parseInt($(".main-slider_js").data("auto")));
			});
		}
	}

	//Compare page Slider
	if ($(".compare-pg").length) {
		var CompareItemsSlider = new Swiper(".compare-pg__items-slider_js", {
			slidesPerView: "auto",
			spaceBetween: 30,
			watchOverflow: true,
			navigation: {
				nextEl: ".compare-pg__slider-arrows .slider-ar:last-child",
				prevEl: ".compare-pg__slider-arrows .slider-ar:first-child"
			},
			breakpointsInverse: true,
			breakpoints: {
				// 1281: {
				1250: {
					spaceBetween: 30
				},
				// 1280: {
				// 	spaceBetween: 20
				// },
				1024: {
					spaceBetween: 20
				},

				768: {
					spaceBetween: 20
				},

				320: {
					spaceBetween: 10
				}
			}
		});

		var CompareCharsSlider = new Swiper(".compare-pg__chars-slider_js", {
			slidesPerView: "auto",
			spaceBetween: 30,
			// // autoHeight: true,
			breakpointsInverse: true,
			watchOverflow: true,
			breakpoints: {
				// 1281: {
				1250: {
					spaceBetween: 30
				},
				1280: {
					spaceBetween: 20
				},
				1024: {
					spaceBetween: 20
				},

				768: {
					spaceBetween: 20
				},

				320: {
					spaceBetween: 10
				}
			}
		});

		if ($(".compare-pg").length) {
			CompareItemsSlider.controller.control = CompareCharsSlider;
			CompareCharsSlider.controller.control = CompareItemsSlider;
		}
	}

	if ($(".items-slider__body").length) {
		// Creating instances of all item sliders with one ititialization script
		//Otherwise we have to creating tens of such init scripts
		//This universal init which suits most of item sliders

		$(".items-slider__body:not(.items-slider__body_cart-cross)").each(function(key, item) {
			//Uniqui name
			var sliderIdName = "sliderItems" + key;

			//Setting id to slider element
			this.id = sliderIdName;

			//Getting name with hash
			var sliderId = "#" + sliderIdName;

			//Setting unique id to parent block
			$(this)
				.closest(".items-slider")
				.attr("id", "items-" + sliderIdName);

			//Getting id of parent block
			var sliderParentElId =
				"#" +
				$(this)
					.closest(".items-slider")
					.attr("id");

			var sliderIdName = new Swiper(sliderId, {
				slidesPerView: "auto",
				// spaceBetween: 30,
				slidesPerGroup: 5,
				watchOverflow: true,
				navigation: {
					prevEl: sliderParentElId + " .items-slider__nav-left",
					nextEl: sliderParentElId + " .items-slider__nav-right"
				},
				breakpoints: {
					// 1281: {
					1250: {
						spaceBetween: 30
					},
					768: {
						spaceBetween: 28,
						slidesPerGroup: 3
					},
					320: {
						// slidesPerView: 2,
						spaceBetween: 10,
						slidesPerGroup: 1
					}
				}
			});
		});

		$(".items-slider").each(function() {
			var $this = $(this);

			if ($this.find(".items-slider__arrow .swiper-button-disabled").length == 2) {
				$this.find(".items-slider__arrow").hide();
			}
		});
	}

	// Cart cross slider initialization
	// if ($(".items-slider__body").length) {
	// 	// Creating instances of all item sliders with one ititialization script
	// 	//Otherwise we have to creating tens of such init scripts
	// 	//This universal init which suits most of item sliders

	// 	$(".items-slider__body_cart-cross").each(function(key, item) {
	// 		//Uniqui name
	// 		var sliderIdName = "sliderItems" + key;

	// 		//Setting id to slider element
	// 		this.id = sliderIdName;

	// 		//Getting name with hash
	// 		var sliderId = "#" + sliderIdName;

	// 		//Setting unique id to parent block
	// 		$(this)
	// 			.closest(".items-slider")
	// 			.attr("id", "items-" + sliderIdName);

	// 		//Getting id of parent block
	// 		var sliderParentElId =
	// 			"#" +
	// 			$(this)
	// 				.closest(".items-slider")
	// 				.attr("id");

	// 		var sliderIdName = new Swiper(sliderId, {
	// 			slidesPerView: "auto",
	// 			// spaceBetween: 30,
	// 			slidesPerGroup: 5,
	// 			watchOverflow: true,
	// 			navigation: {
	// 				prevEl: sliderParentElId + " .items-slider__nav-left",
	// 				nextEl: sliderParentElId + " .items-slider__nav-right"
	// 			},
	// 			breakpoints: {
	// 				1281: {
	// 					spaceBetween: 30
	// 				},
	// 				768: {
	// 					slidesPerView: 3,
	// 					spaceBetween: 20,
	// 					slidesPerGroup: 3
	// 				},
	// 				320: {
	// 					// slidesPerView: 2,
	// 					spaceBetween: 10,
	// 					slidesPerGroup: 2
	// 				}
	// 			}
	// 		});
	// 	});

	// 	$(".items-slider").each(function() {
	// 		var $this = $(this);

	// 		if ($this.find(".items-slider__arrow .swiper-button-disabled").length == 2) {
	// 			$this.find(".items-slider__arrow").hide();
	// 		}
	// 	});
	// }
})();

/* Compare page equilheights * compare.js
=================================*/
$(function() {
	if ($("#compare").length) {
		if (window.matchMedia("(min-width: 768px)").matches) {
			$(".compare-slide-header").equalHeights();
		}

		var collection = [];
		$(".compare-char-list").each(function(i, v) {
			$(v)
				.find(".char-row")
				.each(function(i, v) {
					$(v)
						.addClass("char-row-" + i)
						.equalHeights();
					collection.push("char-row-" + i);
				});
		});

		Array.prototype.forEach.call(collection, function(item) {
			$("." + item).equalHeights();
		});
	}

	$(".compare-pg__options label").on("change", function() {
		$(this)
			.siblings()
			.removeClass("active");
		$(this).addClass("active");
	});

	//Sticking item to top in item page info link page
	if ($(".compare-pg__sticky-header").length) {
		var stickyCompHeader = new Waypoint.Sticky({
			element: $(".compare-pg__sticky-header")[0]
		});
	}
});

//Скрипты в item карточках * item-elements.js
(function() {
	//Добавить количество остальных картинок
	if ($(".item-img-gal").length) {
		$(".item-img-gal").each(function(i, v) {
			var moreItemsCount = 0;
			var $this = $(this);
			$this.find(".item-img-gal__item").each(function(i, v) {
				var currentItem = $(v);
				//Delete other elements
				if (i > 5) {
					// currentItem.remove();
					moreItemsCount++;
				}
				if (i === 5) {
					currentItem
						.find(".item-img-gal__image-wrapper")
						.append(
							'<span class="item-img-gal__more">' +
								'<span class="item-img-gal__more-inner">' +
								'<svg class="icon" width="44" height="32">' +
								'<use xlink: href="#icon-camera"></use>' +
								"</svg>" +
								'<span class="item-img-gal__more-text">еще <span>' +
								moreItemsCount +
								"</span> фото</span>" +
								"</span>" +
								"</span>"
						);
				}
			});
			$this.find(".item-img-gal__more-text span").text(moreItemsCount);
		});
	}

	//Реализация одинаковый высоты блоков в карточках товара
	if (window.matchMedia("(min-width: 768px)").matches) {
		if ($(".item-c_equal").length) {
			$(".item-c_equal .item-c__colors").equalHeights();
			$(".item-c_equal .item-c__categ").equalHeights();
			$(".item-c_equal .item-c__brand-name").equalHeights();
			$(".item-c_equal .item-c__short-descr").equalHeights();
			$(".item-c_equal .item-c__chars").equalHeights();
		}
	}
	//Удаление функциональных кнопок внизу на item-c, 3 виде, в десктопе
	// Это нужно чтобы кнопки корзина и 1 клик правильно располагались.
	if (window.matchMedia("(min-width: 1250px)").matches) {
		$(".item-c_3, .item-c_4").each(function() {
			$(this)
				.find(".item-c__actions-wrapper .item-c__actions")
				.remove();
		});
	}

	// Регулировать z-index других карточек чтобы карточка не появился под других карточек
	// $(".item-c_1,.item-c_2,.item-c_3,.item-c_4,.item-c_5,.item-c_6, .item-c_7").hover(function() {
	// 	$(this)
	// 		.closest(".ui-items__item")
	// 		.siblings()
	// 		.find(".item-c_1,.item-c_2,.item-c_3,.item-c_4,.item-c_5,.item-c_6, .item-c_7")
	// 		// .find(".item-c_2, .item-c_7")
	// 		.toggleClass("lower-z-index");
	// });

	$(".item-c").hover(function() {
		$(this)
			.closest(".ui-items__item")
			.siblings()
			.find(".item-c")
			.toggleClass("lower-z-index");
	});

	$(".swiper-slide .item-c").hover(function() {
		$(this)
			.closest(".swiper-slide")
			.siblings()
			.find(".item-c")
			.toggleClass("lower-z-index");
	});

	//
	$(".pd-equal-item__title").equalHeights();
})();

/*---------Characteristics in Item page * sidebar-toggle-btn.js
============================================*/

(function() {
	$(".has-toggle").each(function() {
		var $this = $(this);
		var qty = $this.data("show-qty");
		var item = $this.find(".show-more-item");

		$this.find(".show-more-item:gt(" + (qty - 1) + ")").hide();

		if (item.length < qty) {
			$(".btn-toggle").hide();
		}
	});

	$(".sidebar-section .btn-toggle").on("click", function(e) {
		e.preventDefault();

		var $this = $(this),
			list = $this.prev(),
			parent = $this.closest(".has-toggle"),
			qty = parent.data("show-qty");

		$this.prev().toggleClass("toggle");

		if (list.hasClass("toggle")) {
			$this.find("span").text($this.data("hide"));
			parent.find(".show-more-item:gt(" + (qty - 1) + ")").show();
		} else {
			$this.find("span").text($this.data("show"));
			parent.find(".show-more-item:gt(" + (qty - 1) + ")").hide();
		}
	});
})();

//Currency * currency.js
(function() {
	$(".currency")
		.on("mouseenter", function() {
			var $this = $(this),
				parent = $this.closest(".currency");

			parent.addClass("active");
		})
		.on("mouseleave", function() {
			var $this = $(this),
				parent = $this.closest(".currency");

			parent.removeClass("active");
		});
})();

/* All popup inits * popups.js
=================================*/
$(function() {
	$(".inline-popup").magnificPopup({
		type: "inline",
		midClick: true,
		removalDelay: 300,
		mainClass: "mfp-zoom-in",
		alignTop: false,
		callbacks: {
			open: function() {
				//Добавляем кнопку Х для закрытия попопа
				$("<a></a>", {
					text: "Закрыт попап",
					href: "#"
				})
					.addClass("b-popup__close ds-hide")
					.prependTo(".mfp-container")
					.on("click", function() {
						$.magnificPopup.close();
					});

				$(".mfp-content").addClass("b-popup-container b-popup-container_default");
			},
			close: function() {
				$(".b-popup__close").remove();
			},
			beforeOpen: function() {
				this.wrap.removeAttr("tabindex");
			}
		}
	});
	//Инициализация только для поиск попапов
	$(".inline-popup-search").magnificPopup({
		type: "inline",
		midClick: true,
		removalDelay: 300,
		mainClass: "mfp-zoom-in",
		alignTop: false,
		focus: ".site-search__input",
		closeOnBgClick: false,
		callbacks: {
			open: function() {
				//Добавляем кнопку Х для закрытия попопа
				$("<a></a>", {
					text: "Закрыт попап",
					href: "#"
				})
					.addClass("b-popup__close")
					.prependTo(".mfp-wrap")
					.on("click", function(e) {
						e.preventDefault();
						$.magnificPopup.close();
					});

				$(".mfp-content").addClass("b-popup-container b-popup-container_default");
				$("body").addClass("search-popup");
				// $('.site-search__input').focus();
			},
			close: function() {
				$(".b-popup__close").remove();
				$("body").removeClass("search-popup");
			}
		}
	});

	$(".account-popup__close").click(function() {
		$.magnificPopup.close();
		return false;
	});

	$(".b-popup__close").click(function() {
		$.magnificPopup.close();
		return false;
	});
});

$(".b-popup-cart__btn-continue").click(function() {
	$.magnificPopup.close();
	return false;
});

/* Toppanel * quickpanel.js
=================================*/
//Revealing quickpanel on scroll
(function() {
	if (typeof Waypoint !== undefined) {
		var $panel = $(".quick-panel");
		var wrapper = document.querySelector(".wrapper");
		var waypoint = new Waypoint({
			element: wrapper || $("body"),
			handler: function(direction) {
				if (direction === "down") {
					$panel.addClass("is-shown");
				} else if (direction === "up") {
					$panel.removeClass("is-shown");
				}
			}
			// context: document.body
		});
		var footer = document.querySelector(".site-footer");
		var waypointUp = new Waypoint({
			element: footer || $("body"),
			handler: function(direction) {
				if (direction === "down") {
					$panel.removeClass("is-shown");
				} else if (direction === "up") {
					$panel.addClass("is-shown");
				}
			}
			// context: document.body
		});
	}
})();

/* Scroll to top * scroll-to-top.js
=================================*/

(function() {
  $(".scroll-to-top").click(function() {
    $("html, body").animate({ scrollTop: 0 }, "slow");
  });

  $(window).scroll(function() {
    var scroll = $(window).scrollTop();

    if (scroll >= 500) {
      $(".scroll-to-top").addClass("show");
    } else {
      $(".scroll-to-top").removeClass("show");
    }
  });
})();

/* Revealing bubble-cart on scroll
=================================*/

(function() {
	function getViewportOffset($e) {
		var $window = $(window),
			scrollLeft = $window && $window.scrollLeft(),
			scrollTop = $window && $window.scrollTop(),
			vOffset = $e && $e.offset();
		return {
			left: vOffset && vOffset.left - scrollLeft,
			top: vOffset && vOffset.top - scrollTop
		};
	}

	var bRow = $(".b-row"),
		bubble = $(".bubble-cart"),
		$panel = $(".bubble-cart"),
		bubbleWidth = bubble.innerWidth(),
		rowCoord = getViewportOffset(bRow),
		rowLeft = rowCoord.left,
		rowWidth = bRow.innerWidth(),
		leftForBubble = rowLeft + (rowWidth - bubbleWidth);

	bubble.css({ left: leftForBubble + "px" });

	var waypoint = new Waypoint({
		element: document.querySelector(".wrapper"),
		handler: function(direction) {
			if (direction === "down") {
				$panel.addClass("is-shown");
			} else if (direction === "up") {
				$panel.removeClass("is-shown");
			}
		}
		// context: document.body
	});
})();

$(function() {
	// SHOP: search autocomplete with some results
	var shop_search_autocomplete_delay = (function() {
		var shop_search_autocomplete_timeout = 0;
		return function(callback, ms) {
			clearTimeout(shop_search_autocomplete_timeout);
			shop_search_autocomplete_timeout = setTimeout(callback, ms);
		};
	})();
	$(".search__form-autocomplete input").each(function() {
		$(this).keyup(function() {
			var size = "48x48"; // size for loaded images
			var min_symbols = 3; // minimum symbols to start a query
			var input = $(this);
			var query = input.val();
			var wrapper = input.closest(".search__form");
			var f = input.closest("form");
			var max_results = f.data("limit");
			var show_images = f.data("images") ? true : false;
			var item_image;
			var url = f.attr("action") + "?view=ajax_search&query=" + query;
			var showall_href = f
				.next(".autocomplete-suggestions")
				.find(".autocomplete-suggestion-showall a")
				.data("href")
				.replace("*", input.attr("name") + "=" + query);
			f.next(".autocomplete-suggestions")
				.find(".autocomplete-suggestion-showall a")
				.attr("href", showall_href);
			if (query.length >= min_symbols) {
				shop_search_autocomplete_delay(function() {
					f.addClass("loading");
					$.get(url, function(html) {
						// clear old result
						$(".autocomplete-suggestions").each(function() {
							$(this)
								.find(".autocomplete-suggestion:not('.autocomplete-suggestion-showall')")
								.remove();
							$(this).hide();
						});
						// format new result
						var tmp = $("<div></div>").html(html);
						if (!tmp.find("#product-list .js-product-list-item").length) {
							f.next(".autocomplete-suggestions").hide();
						} else {
							tmp
								.find("#product-list")
								.find(".js-product-list-item")
								.each(function() {
									if (max_results > 0) {
										if (show_images)
											item_image =
												'<a class="autocomplete__img" href="' +
												$(this)
													.find(".js-item__title")
													.attr("href") +
												'"><img src="' +
												$(this)
													.find(".js-item__image")
													.attr("data-src")
													.replace(/^(.*\/[^\/]+\.)(.*)(\.[^\.]*)$/, "$1" + size + "$3") +
												'" /></a>';
										else item_image = "";
										f.next(".autocomplete-suggestions")
											.find(".autocomplete-suggestion-showall")
											.before(
												'<div class="autocomplete-suggestion">' +
													item_image +
													'<div class="autocomplete__content"><a class="autocomplete__title" href="' +
													$(this)
														.find(".js-item__title")
														.attr("href") +
													'">' +
													$(this)
														.find(".js-item__title")
														.html() +
													"</a>" +
													'    <div class="autocomplete__price">' +
													'      <div class="prc">' +
													'        <div class="prc__i prc__i_reg bold">' +
													$(this)
														.find(".price_main")
														.html() +
													"</div>" +
													"      </div>" +
													"    </div>" +
													"  </div>" +
													"</div>"
											);
										max_results = max_results - 1;
									} else {
										return false;
									}
								});
							f.next(".autocomplete-suggestions").show();
							$(document).bind("click.wrapper", function(e) {
								if ($(e.target).closest(".search").length == 0) {
									$(".autocomplete-suggestions").hide();
									$(e.target)
										.closest(".search")
										.removeClass("is-suggested");
									$(document).unbind("click.wrapper");
								} else {
									$(e.target)
										.closest(".search")
										.addClass("is-suggested");
									$(".search:not('.is-suggested') .autocomplete-suggestions").hide();
									$(e.target)
										.closest(".search")
										.removeClass("is-suggested");
								}
							});
						}
						f.removeClass("loading");
					});
				}, 400);
			} else {
				$(".autocomplete-suggestions").each(function() {
					$(this)
						.find(".autocomplete-suggestion:not('.autocomplete-suggestion-showall')")
						.remove();
					$(this).hide();
				});
				f.removeClass("loading");
			}
			return false;
		});
	});

	$(".js-minicart-wrapper").on("click", ".minicart__delete", function(e) {
		e.preventDefault();
		var $this = $(this),
			$deferred = $.Deferred(),
			$wrapper = $this.closest(".js-minicart-wrapper"),
			$product = $this.closest(".minicart__item"),
			request_data = {
				html: 1,
				items: 1,
				id: $product.data("id")
			};
		if ($product.hasClass("is-loading")) return false;
		else $product.addClass("is-loading").css("opacity", 0.6);
		$.post(
			$wrapper.data("carturl") + "delete/",
			request_data,
			function(response) {
				$deferred.resolve(response);
			},
			"json"
		);
		$deferred.done(function(response) {
			$product.remove();
			$(".js-minicart-count").html(response.data.count);
			$(".js-minicart-total").html(response.data.total);
			if (response.data.count == 0) {
				$(".js-minicart-status, .js-minicart-flystatus")
					.addClass("is-empty")
					.removeClass("not-empty");
				$(".js-flycart-status").addClass("empty");
			} else {
				$(".js-minicart-status, .js-minicart-flystatus")
					.addClass("not-empty")
					.removeClass("is-empty");
				$(".js-flycart-status").removeClass("empty");
			}
		});
	});

	$(document).on("click", ".popup-show_map", function(e) {
		e.preventDefault();
		$.magnificPopup.open({
			items: {
				src: "#address-map"
			},
			type: "inline",
			removalDelay: 0,
			mainClass: "mfp-zoom-in",
			callbacks: {
				open: function() {
					$("<a></a>", { text: "Close", href: "#" })
						.addClass("b-popup__close ds-hide")
						.prependTo(".mfp-container")
						.on("click", function(e) {
							e.preventDefault();
							$.magnificPopup.close();
						});
				},
				close: function() {
					$(".b-popup__close").remove();
				}
			}
		});
	});

	$(".top-message__close-btn").on("click", function(e) {
		e.preventDefault();
		$(".top-message").slideUp();
		$.cookie("balance_hide_alerting", "1", { expires: 7, path: "/" });
	});
});
