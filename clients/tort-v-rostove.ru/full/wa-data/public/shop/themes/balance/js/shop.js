//General scripts for Shop App * general-blog.js
$(function() {
	//Переместь блоки в стр. товара
	if (window.matchMedia("(max-width: 767px)").matches) {
		// $(".pd-cart__qty").appendTo(".pd-cart__mob-qty-stock");
		$(".pd-cart__stock-wrapper").appendTo(".pd-cart__mob-qty-stock");
		$(".pd-cart__options-list").appendTo(".pd-cart__mob-qty-stock");
	}

	//Переместить табы на Странице товара 3
	if (window.matchMedia("(min-width: 1281px)").matches) {
		// $('.item-pg_3 .item-tabs').appendTo('.pd-cart');
	}

	//Reinitializing item tabs flexmenu
	if (window.matchMedia("(min-width: 1250px)").matches) {
		if (".item-pg_3 .pd-cart .item-tabs__list_js".length) {
			$(".item-tabs__list_js").flexMenu({
				linkText: "...",
				cutoff: 0
			});
		}
	}

	//Переместить блок информации на Странице товара 3
	if (window.matchMedia("(max-width: 1249px)").matches) {
		$(".store-info")
			.insertAfter(".item-pg__product")
			.wrap("<div class='item-pg__tab-store-info'></div>");

		$(".pd-descr .pd-tabs")
			.insertAfter(".item-pg__product")
			.wrap("<div class='item-pg__pd-delivery-payment'></div>");
	}
});

//Item page tabs menu * item-tabs-flexmenu.js
(function() {
	/*
		Used plugin - https://github.com/352Media/flexMenu
		But I modified source code to fit my needs.
		Uses flexmenu.js & _flexmenu.scss & _item-tabs.scss(my custom styles on)file
	*/

	// if (window.matchMedia('(min-width: 768px)').matches) {
	$(".item-tabs__list_js").flexMenu({
		linkText: "...",
		cutoff: 1
	});
	// }

	//Just to store uuidv4 ids
	var ids = [];

	$(".item-tabs__list_js .item-tabs__menu-i").each(function() {
		var $this = $(this);

		//uuidv4() - generates random IDs. I used them to get and show
		//appropriate content on tab menu item selecting
		$this.attr("data-id", uuidv4());
		ids.push($this.data("id"));
	});

	$(".item-tabs__content-i").each(function(i, v) {
		$(v).attr("data-id", ids.shift());
	});

	//Item tabs toggle content
	$(".item-tabs__menu-i").on("click", function(e) {
		e.preventDefault();
		var item = $(this),
			contentItem = $(".item-tabs__content-i"),
			itemId = item.data("id");

		contentItem.each(function(i, v) {
			var $this = $(v),
				contentId = $this.data("id");

			if (contentId === itemId) {
				$this
					.add(item)
					.addClass("active")
					.siblings()
					.removeClass("active");

				if (item.closest(".flexMenu-popup").length || $(".flexMenu-viewMore").hasClass("active")) {
					$(".item-tabs__list > li").removeClass("active");
				}
				if (window.matchMedia("(max-width: 767px)").matches) {
					$("body").trigger("click");
				}
			}
		});

		// return false;
	});
})();

//Subcat slider * subcat-elements.js
(function() {
	if (window.matchMedia("(max-width: 767px)").matches) {
		//Preventing init of slider in mobile version
		$(".subcat-slider__container").removeClass("swiper-container");
		$(".subcat-slider__wrapper").removeClass("swiper-wrapper");
		$(".subcat-slider .sub-cat").removeClass("swiper-slide");

		//Show expand all subcategories button in mobile
		var subcat = $(".subcat-wrapper"),
			MIN_ITEM_COUNT = 5,
			toggleBtn = $(".subcat-wrapper__mob-qty-toggle");

		if (subcat.length) {
			// subcat.each(function(i,v){
			var itemsCount = subcat.find(".subcat-wrapper__item").length;

			if (itemsCount < MIN_ITEM_COUNT) {
				toggleBtn.hide();
			}

			toggleBtn.on("click", function(e) {
				var $this = $(this);
				e.preventDefault();

				$this.closest(subcat).toggleClass("show-items");
				$this.toggleClass("active");

				if ($this.hasClass("active")) $this.find("span").text($this.data("hide"));
				else $this.find("span").text($this.data("show"));
			});
			// });
		}
	}

	//Subcategories slider
	if (window.matchMedia("(min-width: 768px)").matches) {
		var subCatSwiper = new Swiper(".subcat-slider__container", {
			slidesPerView: "auto",
			// spaceBetween: 30,
			navigation: {
				nextEl: ".subcat-slider .slider-ar:last-child",
				prevEl: ".subcat-slider .slider-ar:first-child"
			},
			watchOverflow: true,
			freeMode: true,
			breakpoints: {
				1281: {
					spaceBetween: 30
				},
				768: {
					spaceBetween: 20
				}
			}
		});
	}
})();

//Скрипты в Каталоге * catalog-elements.js
(function() {
	//Сортировка в каталоге в мобильном версии
	if (window.matchMedia("(max-width: 767px)").matches) {
		$(".catalog-pg").on("click", ".option-p__sort-col_left", function() {
			$(this)
				.find(".option-p__sort-toggle")
				.toggleClass("active");
		});

		$(".catalog-pg").on("click", ".option-p__qty", function() {
			var $this = $(this);
			$this
				// .find(".option-p__sort-toggle")
				.toggleClass("active");

			$(document).bind("click.wrapper", function(e) {
				if ($(e.target).closest($this).length == 0) {
					// $("body").removeClass("is-overlayed");
					// $(".site-header__cat-btn").removeClass("active");
					$this.removeClass("active");
					$(document).unbind("click.wrapper");
				}
			});
		});
	}
	// Инициализация UI SLIDER
	$(".range-slider__caret").slider({
		range: true,
		min: 0,
		max: 500,
		values: [75, 300]
	});

	$(".filter-wr__header").on("click", function() {
		$(this)
			.toggleClass("active")
			.next()
			.slideToggle();
	});

	// Mobile filter
	(function() {
		// check touch support
		if ("ontouchstart" in window) {
			var click = "touchstart";
		} else {
			var click = "click";
		}

		$(document).on("click", ".catalog-pg__toggle-panel", function(e) {
			e.preventDefault();
			var $this = $(this);
			var btnDataValue = $this.data("sidebar-btn");

			var sidebar;
			$(".catalog-pg__outer-wrapper").each(function(key, value) {
				var $wrapper = $(value);
				var $wrapperDataValue = $(value).data("sidebar");

				if (btnDataValue === $wrapperDataValue) {
					sidebar = $wrapper;
				}
			});

			sidebar
				.addClass("opened", 100)
				.promise()
				.done(function() {
					$(".catalog-pg .bg-overlay").fadeIn(300);
					// $("body, html").addClass("freeze");
				});
		});

		$(".catalog-pg__sidebar-header-close, .bg-overlay").on("click", function(e) {
			e.preventDefault();
			$(".catalog-pg__outer-wrapper")
				.removeClass("opened")
				.promise()
				.done(function() {
					$(".bg-overlay").fadeOut(300);
					$("body, html").removeClass("freeze");
				});
		});
	})();
})();

// Скрипт "Показать еще каталоге фильтр" * catalog-filter-options-toggle.js
(function() {
	var showMoreItems = {
		container: $(".filter-options_more") || null,

		init: function() {
			this.initialShow();
			this.eventListener();
		},

		initialShow: function() {
			this.container.each(function(i, v) {
				var $v = $(v),
					x = parseInt($v.data("qty"));

				$v.find("li:lt(" + x + ")").show();
			});
		},

		eventListener: function() {
			$(".filter-options__qty-toggle").on("click", this.toggleItemsQty);
		},

		toggleItemsQty: function(e) {
			e.preventDefault();
			e.stopPropagation();
			var $this = $(this),
				container = $this.closest(showMoreItems.container);

			//Покажем все
			if (!$this.hasClass("is-shows-all")) {
				var x = parseInt(container.find("li").size());

				container.find("li:lt(" + x + ")").fadeIn();
				$this.addClass("is-shows-all");
				$this.find("span").html($this.data("hide"));
			} else {
				//Вернем как было
				x = parseInt(container.data("qty") - 1);

				container.find("li:gt(" + x + ")").fadeOut();
				$this.removeClass("is-shows-all");
				$this.find("span").html($this.data("show"));
			}
		}
	};
	showMoreItems.init();
})();

/*---------Sliders in Shop App * slider-inits-shop.js
============================================*/

(function() {
	//Item page Main Photo thumbnails in Desktop of Item page 1
	if (window.matchMedia("(min-width: 1250px)").matches) {
		var itemThumbsSlider1Desk = new Swiper(".b-row-ip:not(.b-row-ip_3) .pd-image__thumbs-slider", {
			direction: "vertical",
			slidesPerView: "auto",
			spaceBetween: 20,
			watchOverflow: true,
			navigation: {
				prevEl: ".b-row-ip:not(.b-row-ip_3) .thumb-nav_left",
				nextEl: ".b-row-ip:not(.b-row-ip_3) .thumb-nav_right"
			}
		});
		var itemThumbsSlider3Desk = new Swiper(".b-row-ip_3 .pd-image__thumbs-slider", {
			slidesPerView: "auto",
			spaceBetween: 15,
			navigation: {
				prevEl: ".b-row-ip_3 .thumb-nav_left",
				nextEl: ".b-row-ip_3 .thumb-nav_right"
			}
		});
	}
	//Item page Main Photo thumbnails in Adaptive version of Item page 1
	if (window.matchMedia("(max-width: 1249px)").matches) {
		var itemThumbsSlider1Adap = new Swiper(".pd-image__thumbs-slider", {
			spaceBetween: 20,
			watchOverflow: true,
			navigation: {
				prevEl: ".b-row-ip .thumb-nav_left",
				nextEl: ".b-row-ip .thumb-nav_right"
			},
			breakpoints: {
				// when window width is <= 480px
				// 1280: {
				768: {
					// slidesPerView: 4,
					slidesPerView: "auto",
					spaceBetween: 14
				},
				// when window width is <= 320px
				320: {
					spaceBetween: 12,
					slidesPerView: "auto"
				}
			}
		});
	}

	$(".pd-image__thumbs-slider").on("click", ".swiper-slide", function() {
		var $this = $(this);
		$this.siblings().removeClass("swiper-slide-active");
		$this.addClass("swiper-slide-active");
	});

	if ($(".pd-image__thumbs-slider-nav .swiper-button-disabled").length == 2) {
		$(".pd-image__thumbs-slider-nav").hide();
		$(".pd-image__thumbs").addClass("no-nav");
	}

	//HOme columns mobile slider
	if (window.matchMedia("(max-width: 767px)").matches) {
		var Columnitems = new Swiper(".home-column", {
			slidesPerView: 2,
			spaceBetween: 10,
			watchOverflow: true,
			navigation: {
				prevEl: ".home-column .items-slider__nav-left",
				nextEl: ".home-column .items-slider__nav-right"
			},
			wrapperClass: "home-column__list",
			slideClass: "home-column__item"
		});
	}

	//Home blog mobile slider
	if (window.matchMedia("(max-width: 767px)").matches) {
		var BlogItems = new Swiper(".home-blog_wide", {
			navigation: {
				prevEl: ".home-pg__section_blog .items-slider__nav-left",
				nextEl: ".home-pg__section_blog .items-slider__nav-right"
			},
			wrapperClass: "home-blog__inner",
			slideClass: "home-blog__item"
		});
	}

	//Home brands mobile slider
	if (window.matchMedia("(max-width: 767px)").matches) {
		var BlogItems = new Swiper(".home-brands", {
			slidesPerView: 3,
			spaceBetween: 10,
			watchOverflow: true,
			navigation: {
				prevEl: ".home-pg__section_brands .items-slider__nav-left",
				nextEl: ".home-pg__section_brands .items-slider__nav-right"
			},
			wrapperClass: "home-brands__inner",
			slideClass: "home-brands__item"
		});
	}

	// Creating instances of home promo categories item sliders with one ititialization script
	//Otherwise we have to creating tens of such init scripts
	//This universal init which suits most of item sliders
	$(".home-promo-catgs__sl-wr").each(function(key, item) {
		//Uniqui name
		var sliderIdName = "sliderColored" + key;

		//Setting id to slider element
		this.id = sliderIdName;

		//Getting name with hash
		var sliderId = "#" + sliderIdName;
		var sliderSelector = $(sliderId);
		//Setting unique id to parent block
		$(this)
			.closest(".home-promo-catgs")
			.attr("id", "items-" + sliderIdName);

		//Getting id of parent block
		var sliderParentElId =
			"#" +
			$(this)
				.closest(".home-promo-catgs")
				.attr("id");
		if ($(".col-1-of-5").length) {
			var sliderIdName = new Swiper(sliderId, {
				slidesPerView: "auto",
				spaceBetween: 28,
				slidesPerGroup: 3,
				watchOverflow: true,
				navigation: {
					prevEl: sliderParentElId + " .items-slider__nav-left",
					nextEl: sliderParentElId + " .items-slider__nav-right"
				},
				breakpoints: {
					// 1281: {
					1250: {
						spaceBetween: 28,
						slidesPerGroup: 4
					},
					768: {
						spaceBetween: 28,
						slidesPerGroup: 3
					},
					320: {
						slidesPerView: 2,
						spaceBetween: 10,
						slidesPerGroup: 2
					}
				}
			});
		} else {
			var sliderIdName = new Swiper(sliderId, {
				slidesPerView: "auto",
				spaceBetween: 32,
				slidesPerGroup: 5,
				watchOverflow: true,
				navigation: {
					prevEl: sliderParentElId + " .items-slider__nav-left",
					nextEl: sliderParentElId + " .items-slider__nav-right"
				},
				breakpoints: {
					// 1281: {
					1250: {
						spaceBetween: 28,
						slidesPerGroup: 4
					},
					768: {
						spaceBetween: 28,
						slidesPerGroup: 3
					},
					320: {
						slidesPerView: 2,
						spaceBetween: 10,
						slidesPerGroup: 2
					}
				}
			});
		}
	});

	$(".home-promo-catgs").each(function() {
		var $this = $(this);

		if ($this.find(".slider-arrows .swiper-button-disabled").length == 2) {
			$this.find(".slider-arrows").hide();
		}
	});

	//Home photos slider
	var HomePhotos = new Swiper(".home-fdb-photos_slider", {
		slidesPerView: 4,
		// spaceBetween: 30,
		slidesPerGroup: 4,
		watchOverflow: true,
		navigation: {
			prevEl: ".home-pg__section_feedback-gal .items-slider__nav-left",
			nextEl: ".home-pg__section_feedback-gal .items-slider__nav-right"
		},
		breakpoints: {
			// 1281: {
			1250: {
				spaceBetween: 30
			},
			768: {
				spaceBetween: 20
			},
			320: {
				slidesPerView: 2,
				spaceBetween: 10,
				slidesPerGroup: 2
			}
		}
	});

	//Home subcategories
	var HomeSubcats = new Swiper(".home-subcat-slider", {
		slidesPerView: "auto",

		slidesPerGroup: 8,
		watchOverflow: true,
		navigation: {
			prevEl: ".home-pg__section_subcat-6 .items-slider__nav-left",
			nextEl: ".home-pg__section_subcat-6 .items-slider__nav-right"
		},
		breakpoints: {
			// 1281: {
			1250: {
				spaceBetween: 30
			},
			768: {
				spaceBetween: 22
			},
			320: {
				spaceBetween: 10,
				slidesPerGroup: 2
			}
		}
	});

	// Slider init for promo categories 1

	$(".promo-1-items").each(function(key, item) {
		//Unique name
		var sliderIdName = "sliderPromCat1" + key;

		//Setting id to slider element
		this.id = sliderIdName;

		//Getting name with hash
		var sliderId = "#" + sliderIdName;

		//Setting unique id to parent block
		$(this)
			.closest(".prom-cat-1")
			.attr("id", "items-" + sliderIdName);

		//Getting id of parent block
		var sliderParentElId =
			"#" +
			$(this)
				.closest(".prom-cat-1")
				.attr("id");
		//If there is sidebar
		if ($(".col-1-of-5").length) {
			var sliderIdName = new Swiper(sliderId, {
				slidesPerView: "auto",
				// spaceBetween: 30,
				slidesPerGroup: 3,
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
					1024: {
						slidesPerGroup: 3
					},
					768: {
						slidesPerGroup: 2
					},
					320: {
						spaceBetween: 10,
						slidesPerGroup: 1
					}
				}
			});
		} else {
			var sliderIdName = new Swiper(sliderId, {
				slidesPerView: "auto",
				// spaceBetween: 30,
				slidesPerGroup: 4,
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
					1024: {
						slidesPerGroup: 3
					},
					768: {
						slidesPerGroup: 2
					},
					320: {
						spaceBetween: 10,
						slidesPerGroup: 1
					}
				}
			});
		}
	});
	//Removing nav buttons if less slides
	$(".prom-cat-1").each(function() {
		var $this = $(this);

		if ($this.find(".items-slider__arrow .swiper-button-disabled").length == 2) {
			$this.find(".items-slider__arrow").hide();
		}
	});

	//Home feedbacks slider
	var HomeFeedbacks = new Swiper(".home-pg__section_feedbacks .home-g_slider", {
		slidesPerView: "auto",
		// spaceBetween: 30,
		slidesPerGroup: 3,
		watchOverflow: true,
		navigation: {
			prevEl: ".home-pg__section_feedbacks .items-slider__nav-left",
			nextEl: ".home-pg__section_feedbacks .items-slider__nav-right"
		},
		breakpoints: {
			// 1281: {
			1250: {
				slidesPerGroup: 3
			},
			768: {
				// spaceBetween: 20
				slidesPerGroup: 2
			},
			320: {
				slidesPerView: 1,
				spaceBetween: 0,
				slidesPerGroup: 1
			}
		}
	});

	//Home customer feedbacks slider
	var HomeCustFeedbacks = new Swiper(".home-pg__section_cust-feedbacks .home-g_slider", {
		slidesPerView: "auto",
		// slidesPerGroup: 4,
		watchOverflow: true,
		navigation: {
			prevEl: ".home-pg__section_cust-feedbacks .items-slider__nav-left",
			nextEl: ".home-pg__section_cust-feedbacks .items-slider__nav-right"
		},
		breakpoints: {
			// 1281: {
			1250: {
				slidesPerGroup: 4
			},
			768: {
				slidesPerGroup: 3
			},
			320: {
				slidesPerView: 1,
				spaceBetween: 0,
				slidesPerGroup: 1
			}
		}
	});
})();

///
//Item page image gallery

// var galleryThumbs = new Swiper(".gallery-thumbs", {
// 	spaceBetween: 10,
// 	slidesPerView: 4,
// 	freeMode: true,
// 	watchSlidesVisibility: true,
// 	watchSlidesProgress: true
// });
// var galleryTop = new Swiper(".gallery-top", {
// 	spaceBetween: 10,
// 	navigation: {
// 		nextEl: ".swiper-button-next",
// 		prevEl: ".swiper-button-prev"
// 	},
// 	thumbs: {
// 		swiper: galleryThumbs
// 	}
// });

// $("#product-core-image").on("click", function() {
// 	var photoIndex = 1;

// 	var $this = $(this);

// 	// debugger;
// 	$(".pd-image-gallery__photo-wrapper .swiper-slide").each(function(i, v) {
// 		if ($this.data("startindex") === $(v).data("startindex")) {
// 			photoIndex = i;
// 		}
// 	});
// 	console.log("photoIndex", photoIndex);

// 	$.magnificPopup.open({
// 		items: {
// 			src: "#ip-gallery", // can be a HTML string, jQuery object, or CSS selector
// 			type: "inline"
// 		},
// 		closeBtnInside: true,
// 		removalDelay: 300,
// 		mainClass: "mfp-zoom-in",
// 		callbacks: {
// 			beforeOpen: function() {},
// 			open: function() {
// 				//Добавляем кнопку Х для закрытия попопа
// 				$("<a></a>", {
// 					text: "Закрыт попап",
// 					href: "#"
// 				})
// 					.addClass("b-popup__close ds-hide")
// 					.prependTo(".mfp-container")
// 					.on("click", function() {
// 						$.magnificPopup.close();
// 					});

// 				$(".mfp-content").addClass("b-popup-container b-popup-container_gallery");

// 				var galleryThumbs = new Swiper(".gallery-thumbs", {
// 					spaceBetween: 10,
// 					slidesPerView: 4,
// 					watchSlidesVisibility: true,
// 					watchSlidesProgress: true,
// 					initialSlide: photoIndex,
// 					on: {
// 						init: function() {
// 							var activeSlide = $(this.slides[photoIndex]);

// 							setTimeout(function() {
// 								activeSlide
// 									.addClass("swiper-slide-active swiper-slide-thumb-active")
// 									.siblings()
// 									.removeClass("swiper-slide-active swiper-slide-thumb-active");
// 							}, 0);
// 						}
// 					}
// 				});
// 				var galleryTop = new Swiper(".gallery-top", {
// 					spaceBetween: 10,
// 					initialSlide: photoIndex,
// 					navigation: {
// 						prevEl: ".pd-image-gallery__left",
// 						nextEl: ".pd-image-gallery__right"
// 					},
// 					thumbs: {
// 						swiper: galleryThumbs
// 					}
// 				});
// 			},
// 			close: function() {}
// 		}
// 	});
// });

/*---------Characteristics in Item page * pd-chars.js
============================================*/
(function() {
  $(".pd-chars__show-all").on("click", function(e) {
    $(".item-tabs__menu-i_chars").trigger("click");
  });
})();

//Item page cart tabs * pd-cart-tabs.js
(function() {
	$(".pd-tabs").on("click", ".pd-tabs__tab-menu-item", function(e) {
		e.preventDefault();
		var self = $(this),
			index = self.index();

		self
			.addClass("active")
			.siblings(".pd-tabs__tab-menu-item")
			.removeClass("active");

		var tab = self
			.closest(".pd-tabs")
			.find(".pd-tabs__tab-content-item")
			.eq(index);

		tab
			.fadeIn(150)
			.siblings(".pd-tabs__tab-content-item")
			.hide();

		return false;
	});
})();

//Sticking price into bottom * ip-mobile-price-waypoints.js
$(function() {
	if (window.matchMedia("(max-width: 767px)").matches) {
		if ($(".pd-cart__processing-wrapper").length) {
			var stickyPrice = new Waypoint.Sticky({
				element: $(".pd-cart__processing-wrapper")[0]
			});
		}

		$pricePanel = $(".pd-cart__processing-wrapper");
		var ipMobileCart = new Waypoint({
			element: document.querySelector(".site-footer"),
			handler: function(direction) {
				if (direction === "down") {
					$pricePanel.removeClass("stuck");
				} else if (direction === "up") {
					$pricePanel.addClass("stuck");
				}
			},
			offset: 600
			// context: document.body
		});
	}

	if (window.matchMedia("(max-width: 1249px)").matches) {
		if ($(".item-page .site-header__main").length) {
			var stickyHeader = new Waypoint.Sticky({
				element: $(".site-header__main")[0]
			});
		}

		if ($(".item-tabs__menu").length) {
			var stickyTabs = new Waypoint.Sticky({
				element: $(".item-tabs__menu")[0]
			});
		}
	}
});

//Home page Slider tabs * home-slider-tabs.js
(function() {
	$(".home-tab-sliders").on("click", ".home-tab-sliders__menu .section-title", function(e) {
		e.preventDefault();
		var self = $(this),
			index = self.index();

		self
			.addClass("active")
			.siblings(".section-title")
			.removeClass("active");

		var tab = self
			.closest(".home-tab-sliders")
			.find(".home-tab-sliders__content-item")
			.eq(index);

		tab
			.fadeIn(150, function() {
				$(this).addClass("active");
			})
			.siblings(".home-tab-sliders__content-item")
			.removeClass("active")
			.hide();

		// return false;

		//
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
						1281: {
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
		// $(".items-slider__body").each(function(key, item) {
		// 	//Uniqui name
		// 	var sliderIdName = "sliderItems" + key;

		// 	//Setting id to slider element
		// 	this.id = sliderIdName;

		// 	//Getting name with hash
		// 	var sliderId = "#" + sliderIdName;

		// 	//Setting unique id to parent block
		// 	$(this)
		// 		.closest(".items-slider")
		// 		.attr("id", "items-" + sliderIdName);

		// 	//Getting id of parent block
		// 	var sliderParentElId =
		// 		"#" +
		// 		$(this)
		// 			.closest(".items-slider")
		// 			.attr("id");

		// 	var sliderIdName = new Swiper(sliderId, {
		// 		slidesPerView: "auto",
		// 		// spaceBetween: 30,
		// 		slidesPerGroup: 5,
		// 		navigation: {
		// 			prevEl: sliderParentElId + " .items-slider__nav-left",
		// 			nextEl: sliderParentElId + " .items-slider__nav-right"
		// 		},
		// 		breakpoints: {
		// 			1281: {
		// 				spaceBetween: 30
		// 			},
		// 			1280: {
		// 				// spaceBetween: 28,
		// 				slidesPerGroup: 3
		// 			},
		// 			767: {
		// 				// slidesPerView: 1,
		// 				spaceBetween: 10,
		// 				slidesPerGroup: 1
		// 			},
		// 			320: {
		// 				// slidesPerView: 1,
		// 				spaceBetween: 10,
		// 				slidesPerGroup: 1
		// 			}
		// 		}
		// 	});
		// });
		//
	});
})();

//* promo-cat-flexmenu.js
$(function() {
	$(".prom-flx-menu__list").flexMenu({
		linkText: "...",
		popupClass: "menu-univ-popup univ-dropd",
		cutoff: 0,
		linkTitle: ""
	});
});

//Home faq * home-faq.js
(function() {
  $(".home-faq").on("click", ".home-faq__item", function() {
    var $this = $(this),
      $currentDt = $this.find(".home-faq__content"),
      $items = $this.siblings(),
      $otherDt = $items.find(".home-faq__content");

    if ($otherDt.is(":visible")) {
      $items.removeClass("active");
      $otherDt.slideUp();
    }
    $this.toggleClass("active");
    $currentDt.slideToggle();
  });
})();

var updateHeaderCart = (function($) {
	$(document).ready(function() {
		updateHeaderCart = function(data) {
			if (data["count"] > 0) {
				$(".js-minicart-count").html(data["count"]);
				$(".js-minicart-total").html(data["total"]);
				$(".js-minicart-status")
					.removeClass("is-empty")
					.addClass("not-empty");
				$(".js-minicart-flystatus").removeClass("is-empty");
				$(".js-flycart-status").removeClass("empty");
			} else {
				$(".js-minicart-status")
					.removeClass("not-empty")
					.addClass("is-empty");
				$(".js-minicart-flystatus").addClass("is-empty");
				$(".js-flycart-status").addClass("empty");
			}
			if ("items" in data) {
				var html = "";
				var image = "";
				for (var i = 0; i < data["items"].length; ++i) {
					image = data["items"][i]["image_url"];
					image = !image || image.charAt(image.length - 1) == "." ? $(".js-minicart-wrapper").data("dummyimg") : image;
					html +=
						'<li class="minicart__item" data-id="' +
						data["items"][i]["id"] +
						'">' +
						'	<div class="mini-item">' +
						'		<a class="mini-item__image" href="' +
						data["items"][i]["frontend_url"] +
						'">' +
						'			<img src="' +
						image +
						'" />' +
						"		</a>" +
						'		<div class="mini-item__content"><a class="mini-item__name" href="' +
						data["items"][i]["frontend_url"] +
						'">' +
						data["items"][i]["name"] +
						"</a>" +
						'			<div class="mini-item__price-list">' +
						'				<div class="mini-item__price mini-item__price_regl">' +
						"					<span>" +
						data["items"][i]["price"] +
						"</span>" +
						"					<span>x</span>" +
						"					<span>" +
						data["items"][i]["quantity"] +
						"</span>" +
						"				</div>" +
						"			</div>";
					if (data["items"][i]["services"].length) {
						html += '	<div class="mini-item__extra">';
						for (var j = 0; j < data["items"][i]["services"].length; ++j) {
							html +=
								'<div class="mini-item__extra-item">' +
								"				<span>+ " +
								data["items"][i]["services"][j]["name"] +
								"</span>" +
								"				<strong> " +
								data["items"][i]["services"][j]["price"] +
								"</strong>" +
								"				<span> x</span>" +
								"				<span>" +
								data["items"][i]["services"][j]["quantity"] +
								"</span>" +
								"			</div>";
						}
						html += "	</div>";
					}
					html +=
						"</div>" +
						"	</div>" +
						'	<div class="minicart__delete">' +
						'		<button class="close-x">' +
						'			<svg class="icon cent-icon" width="8" height="8">' +
						'				<use xlink:href="#arrow-x"></use>' +
						"			</svg>" +
						"		</button>" +
						"	</div>" +
						"</li>";
				}
				$(".js-minicart-wrapper .minicart__list").html(html);
			}
		};

		return updateHeaderCart;
	});
})(jQuery);

(function() {
	// Promos countdown
	if ($.fn.countdown) {
		$(".countdown__timer").each(function() {
			var $this = $(this);
			var id = $this.attr("id") || "promo-timer__countdown" + ("" + Math.random()).slice(2);
			$this.attr("id", id);
			var date = $this.data("end").replace(/-/g, "/");
			$this.countdown(
				{
					date: date,
					format: "on"
				},
				function() {
					// callback function
				}
			);
		});
	}

	//PRODUCT FILTERING
	var f = function() {
		var ajax_form_callback = function(f) {
			var fields = f.serializeArray();
			var params = [];
			for (var i = 0; i < fields.length; i++) {
				if (fields[i].value !== "") {
					params.push(fields[i].name + "=" + fields[i].value);
				}
			}
			var url = "?" + params.join("&");
			$(".catalog-pg__items").addClass("loading");
			$.get(url + "&_=_", function(html) {
				var tmp = $("<div></div>").html(html);
				$(".catalog-pg__content").html(tmp.find(".catalog-pg__content").html());
				$(".catalog-pg__items").removeClass("loading");
				if (!!(history.pushState && history.state !== undefined)) {
					window.history.pushState({}, "", url);
				}
				if (lazyLoadInstance) {
					lazyLoadInstance.update();
				}
				var tooltips = document.querySelectorAll(".has-tooltip"),
					tooltipText;

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
			});
		};

		$(".catalog-pg__filter-v input").change(function() {
			ajax_form_callback($(this).closest("form"));
		});
		$(".catalog-pg__filter-v").submit(function() {
			ajax_form_callback($(this));
			return false;
		});

		$(".catalog-pg__filter-v .range-slider").each(function() {
			if (!$(this).find(".range-slider__caret").length) {
				$(this).append('<div class="range-slider__caret"></div>');
			} else {
				return;
			}
			var min = $(this).find(".filter-range__min");
			var max = $(this).find(".filter-range__max");
			var min_value = parseFloat(min.attr("placeholder"));
			var max_value = parseFloat(max.attr("placeholder"));
			var step = 1;
			var slider = $(this).find(".range-slider__caret");
			if (slider.data("step")) {
				step = parseFloat(slider.data("step"));
			} else {
				var diff = max_value - min_value;
				if (Math.round(min_value) != min_value || Math.round(max_value) != max_value) {
					step = diff / 10;
					var tmp = 0;
					while (step < 1) {
						step *= 10;
						tmp += 1;
					}
					step = Math.pow(10, -tmp);
					tmp = Math.round(100000 * Math.abs(Math.round(min_value) - min_value)) / 100000;
					if (tmp && tmp < step) {
						step = tmp;
					}
					tmp = Math.round(100000 * Math.abs(Math.round(max_value) - max_value)) / 100000;
					if (tmp && tmp < step) {
						step = tmp;
					}
				}
			}
			slider.slider({
				range: true,
				min: parseFloat(min.attr("placeholder")),
				max: parseFloat(max.attr("placeholder")),
				step: step,
				values: [
					parseFloat(min.val().length ? min.val() : min.attr("placeholder")),
					parseFloat(max.val().length ? max.val() : max.attr("placeholder"))
				],
				slide: function(event, ui) {
					var v = ui.values[0] == $(this).slider("option", "min") ? "" : ui.values[0];
					min.val(v);
					v = ui.values[1] == $(this).slider("option", "max") ? "" : ui.values[1];
					max.val(v);
				},
				stop: function(event, ui) {
					min.change();
				}
			});
			min.add(max).change(function() {
				var v_min = min.val() === "" ? slider.slider("option", "min") : parseFloat(min.val());
				var v_max = max.val() === "" ? slider.slider("option", "max") : parseFloat(max.val());
				if (v_max >= v_min) {
					slider.slider("option", "values", [v_min, v_max]);
				}
			});
		});
	};
	f();

	//ADD TO CART
	$(document).on("click", "form.addtocart a.js-addtocart-submit", function(e) {
		e.preventDefault();
		$(this)
			.closest("form")
			.trigger("submit");
	});
	$(document).on("submit", "form.addtocart", function() {
		var f = $(this);
		f.find("button:submit, input:submit")
			.addClass("is-adding-cart")
			.attr("disabled", "disabled");
		f.closest(".pd-equal-item").addClass("is-loading");
		f.find(".side-item").addClass("is-loading");
		if (f.data("url")) {
			$.get(f.data("url"), function(html) {
				$("#extend-purchase .b-popup-it-opt__content").html(html);
				$("#extend-purchase .b-popup-it-opt__title").html(f.data("title"));
				if (typeof jQuery.fn.stylizeInput === "function") {
					$("#extend-purchase input[type=checkbox],#extend-purchase input[type=radio]").stylizeInput();
				}
				var tooltips = document.querySelectorAll(".has-tooltip"),
					tooltipText;

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
				$.magnificPopup.open({
					items: {
						src: "#extend-purchase"
					},
					type: "inline",
					removalDelay: 0,
					mainClass: "mfp-zoom-in",
					callbacks: {
						beforeOpen: function() {
							this.wrap.removeAttr("tabindex")
						},
						open: function() {
							$("<a></a>", { text: "Close", href: "#" })
								.addClass("b-popup__close ds-hide")
								.prependTo(".mfp-container")
								.on("click", function() {
									$.magnificPopup.close();
								});
						},
						close: function() {
							$(".b-popup__close").remove();
						}
					}
				});
				f.find("button:submit, input:submit")
					.removeClass("is-adding-cart")
					.removeAttr("disabled");
				f.closest(".pd-equal-item").removeClass("is-loading");
				f.find(".side-item").removeClass("is-loading");
				$(".cart-popup__close").click(function() {
					$.magnificPopup.close();
					return false;
				});
			});
			return false;
		}
		var _p_title = f.data("title"),
			_p_price = f.data("price"),
			_p_oldprice = f.data("oldprice"),
			_p_image = f.data("image"),
			_p_qty = f.find(".qty__inner input").val();
		$.post(
			f.attr("action") + "?items=1&html=1",
			f.serialize(),
			function(response) {
				f.find("button:submit, input:submit")
					.removeClass("is-adding-cart")
					.removeAttr("disabled");
				f.closest(".pd-equal-item").removeClass("is-loading");
				f.find(".side-item").removeClass("is-loading");
				if (response.status == "ok") {
					$("#added-to-cart .js-item__title").html(_p_title);
					$("#added-to-cart .b-popup-cart__price-new").html(_p_price);
					if (_p_oldprice.length > 0) $("#added-to-cart .b-popup-cart__price-old").html(_p_oldprice);
					else
						$("#added-to-cart .b-popup-cart__price-old")
							.html("")
							.hide();
					$("#added-to-cart .b-popup-cart__image img").attr("src", _p_image);
					if (parseInt(_p_qty) > 1)
						$("#added-to-cart .js-item__quantity")
							.show()
							.find("span")
							.html(_p_qty);
					else $("#added-to-cart .js-item__quantity").hide();
					// Update cart counters
					updateHeaderCart(response.data);
					// construct popup
					if ($(".b-popup_cart-1").length) {
						// big popup
						$.magnificPopup.open({
							items: {
								src: "#added-to-cart"
							},
							type: "inline",
							removalDelay: 300,
							mainClass: "mfp-zoom-in",
							callbacks: {
								open: function() {
									$("<a></a>", { text: "Close", href: "#" })
										.addClass("b-popup__close ds-hide")
										.prependTo(".mfp-container")
										.on("click", function() {
											$.magnificPopup.close();
										});
									$(".mfp-content").addClass("b-popup-container b-popup-container_default");
								},
								close: function() {
									$(".b-popup__close").remove();
								}
							}
						});
					} else if ($(".b-popup_cart-2").length) {
						// fixed top popup
						if (typeof _balance_added_to_cart_timer == "number") clearInterval(_balance_added_to_cart_timer);

						$(".b-popup_cart-2").addClass("is-shown");
						var countNum = parseInt($(".b-popup-cart__notif .countdown").data("ttl"));
						if (countNum <= 0) countNum = 5;

						$(".b-popup-cart__notif .countdown").html(countNum);

						_balance_added_to_cart_timer = setInterval(function() {
							if (countNum === 0) {
								$(".b-popup_cart-2").removeClass("is-shown");
								clearInterval(_balance_added_to_cart_timer);
							} else {
								countNum--;
								$(".b-popup-cart__notif .countdown").html(countNum);
							}
						}, 1000);
						$(".b-popup-cart__close-btn").on("click", function() {
							$(".b-popup_cart-2").removeClass("is-shown");
							clearInterval(_balance_added_to_cart_timer);
						});
					}
				} else if (response.status == "fail") {
					alert(response.errors);
				}
			},
			"json"
		);
		return false;
	});

	// Compare add/remove
	$(document).on("click", ".btn-compare", function(e) {
		e.preventDefault();
		var product = $(this).data("product");
		var compare = $.cookie("shop_compare");
		$.cookie("shop_compare", compare, { expires: 30, path: "/" });
		if (!$(this).hasClass("active")) {
			// add
			var tooltip_text = $(this).data("active");
			if (compare) {
				var i = $.inArray(product + "", compare.split(","));
			} else {
				var i = -1;
			}
			if (i == -1) {
				if (compare) {
					compare += "," + product;
				} else {
					compare = "" + product;
				}
			}
			if (compare.split(",").length > 1) {
				var url = $(this)
					.data("url")
					.replace(/compare\/.*$/, "compare/" + compare + "/");
			} else {
				var url = "javascript:void(0);";
			}
			// update counters
			var compare_count = compare.split(",").length;
			$.cookie("shop_compare", compare, { expires: 30, path: "/" });
			$(".btn-compare-" + product).addClass("active");
			// show popup
			if (compare_count > 1 && $("#compare-popup").length) {
				$("#compare-popup .compare-popup-count").html("(" + compare_count + ")");
				$("#compare-popup .js-compare-link").attr("href", url);
				$("#compare-popup .js-compare-popup-productimg").attr("src", $(this).data("product_image"));
				$("#compare-popup .js-compare-popup-productname").html($(this).data("product_name"));
				$("#compare-popup .js-compare-popup-productlink").attr("href", $(this).data("product_url"));
				if (typeof _balance_added_to_compare_timer == "number") clearInterval(_balance_added_to_compare_timer);

				$("#compare-popup").addClass("is-shown");
				var countNum = parseInt($("#compare-popup").data("ttl"));
				if (countNum <= 0) countNum = 5;

				_balance_added_to_compare_timer = setInterval(function() {
					if (countNum === 0) {
						$("#compare-popup").removeClass("is-shown");
						clearInterval(_balance_added_to_compare_timer);
					} else {
						countNum--;
						//$(".b-popup-cart__notif .countdown").html(countNum);
					}
				}, 1000);
				$("#compare-popup .popup-compare__close-btn").on("click", function() {
					$("#compare-popup").removeClass("is-shown");
					clearInterval(_balance_added_to_compare_timer);
				});
			}
		} else {
			if (typeof _balance_added_to_compare_timer == "number") {
				clearInterval(_balance_added_to_compare_timer);
				$("#compare-popup").removeClass("is-shown");
			}
			var tooltip_text = $(this).data("title");
			if (compare) {
				compare = compare.split(",");
			} else {
				compare = [];
			}
			var i = $.inArray(product + "", compare);
			if (i != -1) {
				compare.splice(i, 1);
			}
			if (compare.length > 1) {
				var url = $(this)
					.data("url")
					.replace(/compare\/.*$/, "compare/" + compare + "/");
				$.cookie("shop_compare", compare.join(","), { expires: 30, path: "/" });
			} else if (compare.length == 1) {
				var url = "javascript:void(0);";
				$.cookie("shop_compare", compare.join(","), { expires: 30, path: "/" });
			} else {
				$.cookie("shop_compare", null, { expires: 0, path: "/" });
			}
			var compare_count = compare.length;
			$(".btn-compare-" + product).removeClass("active");
		}
		$(this)
			.find(".b-tooltip")
			.text(tooltip_text);
		$(".js-compare-count").html(compare_count);
		if (compare_count > 1) {
			$(".js-compare-status").addClass("not-empty");
		} else {
			$(".js-compare-status").removeClass("not-empty");
		}
		$(".js-compare-link").attr("href", url);
	});
	// Favorite add/remove
	$(document).on("click", ".btn-fav", function(e) {
		e.preventDefault();
		var product = $(this).data("product");
		var fav = $.cookie("shop_favorite");
		$.cookie("shop_favorite", fav, { expires: 30, path: "/" });
		if (!$(this).hasClass("active")) {
			// add
			var tooltip_text = $(this).data("active");
			if (fav) {
				var i = $.inArray(product + "", fav.split(","));
			} else {
				var i = -1;
			}
			if (i == -1) {
				if (fav) {
					fav += "," + product;
				} else {
					fav = "" + product;
				}
			}
			var wishlist_count = fav.split(",").length;
			$.cookie("shop_favorite", fav, { expires: 30, path: "/" });
			$(".btn-fav-" + product).addClass("active");
		} else {
			var tooltip_text = $(this).data("title");
			if (fav) {
				fav = fav.split(",");
			} else {
				fav = [];
			}
			var i = $.inArray(product + "", fav);
			if (i != -1) {
				fav.splice(i, 1);
			}
			if (fav) {
				$.cookie("shop_favorite", fav.join(","), { expires: 30, path: "/" });
			} else {
				$.cookie("shop_favorite", null);
			}
			var wishlist_count = fav.length;
			$(".btn-fav-" + product).removeClass("active");
		}
		if (wishlist_count > 0) {
			$(".js-wishlist-status").addClass("not-empty");
		} else {
			$(".js-wishlist-status").removeClass("not-empty");
		}
		$(".js-wishlist-count").html(wishlist_count);
		$(this)
			.find(".b-tooltip")
			.text(tooltip_text);
	});
	// Changing products view mode
	$(document).on("click", ".option-p__item-type", function(e) {
		e.preventDefault();
		var url = window.location.href;
		var _theme_products_view_mode = $(this).data("type");
		$.cookie("_theme_products_view_mode", _theme_products_view_mode, { expires: 30, path: "/" });
		$(".option-p__item-type.active").removeClass("active");
		$(this).addClass("active");
		//$(window).lazyLoad && $(window).lazyLoad('sleep');
		$(".catalog-pg__items").addClass("loading");
		$.get(url, function(html) {
			var tmp = $("<div></div>").html(html);
			$(".catalog-pg__content").html(tmp.find(".catalog-pg__content").html());
			$(".catalog-pg__items").removeClass("loading");
			if (lazyLoadInstance) {
				lazyLoadInstance.update();
			}
			var tooltips = document.querySelectorAll(".has-tooltip"),
				tooltipText;

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
		});
	});
	// Quickview
	$(document).on("click", ".btn-quickview", function(e) {
		e.preventDefault();
		var b = $(this);
		b.closest(".item-c, .item-list-c, .item-line-c").addClass("is-loading");
		if (b.data("url")) {
			$.get(b.data("url"), function(html) {
				var tmp = $("<div></div>").html(html);
				$("#quickview-popup .item-pg").html(tmp.find(".item-pg").html());
				if (lazyLoadInstance) {
					lazyLoadInstance.update();
				}
				if (typeof jQuery.fn.stylizeInput === "function") {
					$("#quickview-popup input[type=checkbox],#quickview-popup input[type=radio]").stylizeInput();
				}
				var tooltips = document.querySelectorAll(".has-tooltip"),
					tooltipText;

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
				$.magnificPopup.open({
					items: {
						src: "#quickview-popup"
					},
					type: "inline",
					removalDelay: 300,
					mainClass: "mfp-zoom-in",
					callbacks: {
						open: function() {
							$("<a></a>", { text: "Close", href: "#" })
								.addClass("b-popup__close ds-hide")
								.prependTo(".mfp-container")
								.on("click", function() {
									$.magnificPopup.close();
								});
							$(".mfp-content").addClass("b-popup-container  b-popup-container_fastview");
						},
						close: function() {
							$(".b-popup__close").remove();
						}
					}
				});
				b.closest(".item-c, .item-list-c, .item-line-c").removeClass("is-loading");
			});
		}
	});

	/*
	//Реализация одинаковый высоты блоков в карточках товара
	if (window.matchMedia("(min-width: 768px)").matches) {
		if ($(".item-c_equal").length) {
			var inline = 0;
			var offsettop = 0;
			$(".item-c_equal").each(function(){
				if(inline == 0) {
					offsettop = $(this).offset().top;
				}
				if($(this).offset().top > offsettop)
					return false;
				inline++;
			});
			var total = $(".item-c_equal").closest(".ui-items").length;
			var equalPerLine = function(from,to,inline,total){
				console.log("from:"+from+"; to:"+to+"; inline:"+inline+"; total:"+total);
				var rows = [{descr:0,chars:0}];
				for(i=from;i<=to;++i) {
					if(rows[0].descr < $(".item-c_equal").closest(".ui-items").find(".ui-items__item:nth-child("+i+") .item-c__short-descr").height())
						rows[0].descr = $(".item-c_equal").closest(".ui-items").find(".ui-items__item:nth-child("+i+") .item-c__short-descr").height();
					if(rows[0].chars < $(".item-c_equal").closest(".ui-items").find(".ui-items__item:nth-child("+i+") .item-c__chars").height())
						rows[0].chars = $(".item-c_equal").closest(".ui-items").find(".ui-items__item:nth-child("+i+") .item-c__chars").height();
				}
				for(i=from;i<=to;++i) {
					$(".item-c_equal").closest(".ui-items").find(".ui-items__item:nth-child("+i+") .item-c__short-descr").height(rows[0].descr);
					$(".item-c_equal").closest(".ui-items").find(".ui-items__item:nth-child("+i+") .item-c__chars").height(rows[0].chars);
				}
				if(from < total)
					equalPerLine((to + 1),(to + inline),inline,total);
			};
			equalPerLine(1,inline,inline,10);
		}
	}
	*/

	$(document).on("click", ".qty__btn_decr, .qty__btn_incr", function(e) {
		e.preventDefault();
		var input = $(this)
			.closest(".qty__inner")
			.find("input");
		if ($(this).hasClass("qty__btn_decr")) var new_val = parseInt(input.val()) - 1;
		else if ($(this).hasClass("qty__btn_incr")) var new_val = parseInt(input.val()) + 1;
		if (new_val <= 0) new_val = 1;
		$(this)
			.closest(".qty__inner")
			.find("input")
			.val(new_val)
			.trigger("change");
	});

	// Viewed products TODO:re
	if ($("body").data("viewed")) {
		var product = $("body").data("viewed");
		var balance_viewed = $.cookie("balance_viewed");
		$.cookie("balance_viewed", balance_viewed, { expires: 30, path: "/" });
		if (balance_viewed) {
			var i = $.inArray(product + "", balance_viewed.split(","));
		} else {
			var i = -1;
		}
		if (i == -1) {
			if (balance_viewed) {
				balance_viewed += "," + product;
			} else {
				balance_viewed = "" + product;
			}
		}
		$.cookie("balance_viewed", balance_viewed, { expires: 30, path: "/" });
	}
	$(document).on("click", ".clear-viewed-history", function(e) {
		e.preventDefault();
		$.cookie("balance_viewed", null);
		$(".viewed-history-wrapper").remove();
	});

	$(document).on("click", ".catalog-pg__options .drop-list__link", function(e) {
		e.preventDefault();
		$.cookie("products_per_page", $(this).text(), { expires: 30, path: "/" });
		var url = window.location.search.replace(/(page=)(\w+)/g, "page=1");
		$(".catalog-pg__items").addClass("loading");
		$.get(url, function(html) {
			var tmp = $("<div></div>").html(html);
			$(".catalog-pg__content").html(tmp.find(".catalog-pg__content").html());
			$(".catalog-pg__items").removeClass("loading");
			if (!!(history.pushState && history.state !== undefined)) {
				window.history.pushState({}, "", url);
			}
			if (lazyLoadInstance) {
				lazyLoadInstance.update();
			}
			var tooltips = document.querySelectorAll(".has-tooltip"),
				tooltipText;

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
		});
	});
})();
