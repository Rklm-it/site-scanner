/*
 * jQuery jCarouselLite
 * Version: 1.0.1
 */

(function($) {				// Compliant with jquery.noConflict()
$.fn.jCarouselLite = function(o) {
	o = $.extend({
		btnPrev: null,		// Параметр, указывающий на класс или id кнопки, который ведет сразу к предыдущему элементу [".prev"]
		btnNext: null,		// Параметр, указывающий на класс или id кнопки, который ведет сразу к следующему элементу [".next"]
		btnGo: null,		// Параметр, указывающий на классы или id кнопок, которые ведут сразу к определенному элементу галереи [".0", ".1", ".2"]

		auto: null,		// Время через которое галлерея автоматически прокрутится [1сек = 1000]
		hoverPause: false,	// При наведении на элемент галереи останавливается автоматическая прокрутка [false - не останавливать, true - останавливать]
		mouseWheel: false,	// Включает прокрутку колесиком мышки, необходим mousewheel.js [false - выключено, true - включено]

		speed: 500,		// Скорость пролистывания [1сек = 1000]
		easing: null,		// Дергающийся эффект, необходим easing.js ["easeOutElastic"]

		vertical: false,	// Включает вертикальное отображение, по умолчанию горизонтальная [false - горизонтальное, true - вертикальное]
		circular: true,		// Отключает цикл, по умолчнию включен [false - выключено, true - включено]
		visible: 1,		// Количество отображаемых элементов
		start: 0,		// С какого элемента начинать показывать
		scroll: 1,		// Сколько элементов прокручивает за одно нажатие или прокрутку колесиком мышки

		beforeStart: null,	// Обратная функция начала показа, выполняется сразу же при перелистывании [function(a) {alert("Before animation starts:" + a);]
		afterEnd: null		// Обратная функция конца показа, срабатывает сразу после завершения перелистывания [function(a) {alert("After animation ends:" + a);]
    }, o || {});

    return this.each(function() {	// Returns the element collection. Chainable.

        var running = false, animCss=o.vertical?"top":"left", sizeCss=o.vertical?"height":"width";
        var div = $(this), ul = $("ul", div), tLi = $("li", ul), tl = tLi.size(), v = o.visible;

        if(o.circular) {
            ul.prepend(tLi.slice(tl-v+1).clone()) // add last visible part, to the begin of the ul 
              .append(tLi.slice(0,o.scroll).clone());  // add first visble part, to the end of the ul
            o.start += v-1; //the script added an item at the front, move the start position with one part
        }

        var li = $("li", ul), itemLength = li.size(), curr = o.start;
        div.css("visibility", "visible");

        li.css({overflow: "hidden", float: o.vertical ? "none" : "left"});
        ul.css({margin: "0", padding: "0", position: "relative", "list-style-type": "none", "z-index": "1"});
        div.css({overflow: "hidden", position: "relative", "z-index": "2", left: "0px"});

        var liSize = o.vertical ? height(li) : width(li);   // Full li size(incl margin)-Used for animation
        var ulSize = liSize * itemLength;                   // size of full ul(total length, not just for the visible items)
        var divSize = liSize * v;                           // size of entire div(total length for just the visible items)

        li.css({width: li.width(), height: li.height()});
        ul.css(sizeCss, ulSize+"px").css(animCss, -(curr*liSize));

        div.css(sizeCss, divSize+"px");                     // Width of the DIV. length of visible images

        if(o.btnPrev) {
            $(o.btnPrev).click(function() {
                return go(curr-o.scroll);
            });
            //not needed (scriptbreaker)
            /*
            if(o.hoverPause) {
                $(o.btnPrev).hover(function(){stopAuto();}, function(){startAuto();});
            }
            */
        }


        if(o.btnNext) {
            $(o.btnNext).click(function() {
                return go(curr+o.scroll);
            });
            //not needed (scriptbreaker)
            /*
            if(o.hoverPause) {
                $(o.btnNext).hover(function(){stopAuto();}, function(){startAuto();});
            }
            */
        }

        if(o.btnGo)
            $.each(o.btnGo, function(i, val) {
                $(val).click(function() {
                	//added by the scriptbreaker extension
                	return go(o.circular ? (o.visible+i-1) : i);
                	
                	//why is that?
                	//return go(o.circular ? o.visible+i : i);
                });
            });

        if(o.mouseWheel && div.mousewheel)
            div.mousewheel(function(e, d) {
                return d>0 ? go(curr-o.scroll) : go(curr+o.scroll);
            });

        var autoInterval;

        function startAuto() {
          stopAuto();
          autoInterval = setInterval(function() {
                  go(curr+o.scroll);
              }, o.auto+o.speed);
        };

        function stopAuto() {
            clearInterval(autoInterval);
        };

        if(o.auto) {
            if(o.hoverPause) {
            	//scriptbreaker extention add the hover pause to the children instead of the element itself
                div.children().hover(function(){stopAuto();}, function(){startAuto();});
            }
            startAuto();
        };

        function vis() {
            return li.slice(curr).slice(0,v);
        };

        function go(to) {
            if(!running) {
            	
                if(o.beforeStart)
                    o.beforeStart.call(this, vis());

                if(o.circular) {            // If circular we are in first or last, then goto the other end
                    if(to<0) {           // If before range, then go around
                        ul.css(animCss, -( (curr + tl) * liSize)+"px");
                        curr = to + tl;
                    } else if(to>itemLength-v) { // If beyond range, then come around
                        ul.css(animCss, -( (curr - tl) * liSize ) + "px" );
                        curr = to - tl;
                    } else curr = to;
                } else {                    // If non-circular and to points to first or last, we just return.
                    if(to<0 || to>itemLength-v) return;
                    else curr = to;
                }                           // If neither overrides it, the curr will still be "to" and we can proceed.

                running = true;

                ul.animate(
                    animCss == "left" ? { left: -(curr*liSize) } : { top: -(curr*liSize) } , o.speed, o.easing,
                    function() {
                        if(o.afterEnd)
                            o.afterEnd.call(this, vis(), curr, o.btnGo);
                        running = false;
                    }
                );
                // Disable buttons when the carousel reaches the last/first, and enable when not
                if(!o.circular) {
                    $(o.btnPrev + "," + o.btnNext).removeClass("disabled");
                    $( (curr-o.scroll<0 && o.btnPrev)
                        ||
                       (curr+o.scroll > itemLength-v && o.btnNext)
                        ||
                       []
                     ).addClass("disabled");
                }

            }
            return false;
        };
    });
};

function css(el, prop) {
    return parseInt($.css(el[0], prop)) || 0;
};
function width(el) {
    return  el[0].offsetWidth + css(el, 'marginLeft') + css(el, 'marginRight');
};
function height(el) {
    return el[0].offsetHeight + css(el, 'marginTop') + css(el, 'marginBottom');
};

})(jQuery);