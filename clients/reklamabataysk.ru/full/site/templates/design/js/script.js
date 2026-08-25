(function($) {
	
	/* ------ Accordion ------ */
	$('.accordion > dt:first').addClass('link_active');
	$('.accordion > dd:not(:first)').hide();
	$('.accordion > dt').click(function() {
		if ( $(this).hasClass('link_active') ) {
			$(this).removeClass('link_active').next().stop().slideUp(200);
		} else {
			$('.accordion > dt').removeClass('link_active');
			$('.accordion > dd').stop().slideUp(200);
			$(this).addClass('link_active').next().stop().slideDown(200);
		}	
		return false;
	});

	/* ------ Yandex map ------ */
	$('.map').each(function(){
		// blocks and vars
		var $map = $(this),
			latitude = parseFloat($map.data('latitude')),
			longitude = parseFloat($map.data('longitude')),
			zoom = parseInt($map.data('zoom'),10) || 15,
			iconHref = $map.data('icon');
		// init map
		ymaps.ready(function () {
			// craete map
			var map = new ymaps.Map($map.attr('id'), {
				center: [latitude, longitude],
				zoom: zoom,
				controls: ['zoomControl','routeEditor','typeSelector','fullscreenControl'],
			});
			// disable ScrollZoom
			map.behaviors.disable("scrollZoom");
			// balloon template
			var getPhones = function(arr) {
				var result;
				for (var i = 0; i < properties.phone.length(); i++ ){
					result += properties.phone[i] + '<br>';
				}
				return result;
			}				
			var MyBalloonContentLayoutClass = ymaps.templateLayoutFactory.createClass(
				'<a class="fancybox" href="{{ properties.img }}">' +
					'<img src="{{ properties.img }}" width="200">' + 
				'</a>'+
				'{% if properties.isPrizmatron %}<p class="baloon__board-prizm">Призматрон</p>{% endif %}' +
				'<p>{{ properties.address }}</p>' +
				'<p class="baloon__free-date">{{ properties.free }}</p>' +
				'<p>{% for phone in properties.phone %}' +
					 '{{ phone }}<br>' +
				 '{% endfor %}</p>'
			);
			//ymaps.layout.storage.add('my#layout', MyBalloonContentLayoutClass);
			// user's objects
			$.getJSON( "json/geoObjects.php", function( data ) {
				var iconCounter = 0;
				$.each( data, function( key, val ) {
					var placemark = new ymaps.Placemark( val['coord'],
						// placemark properties
						{
							iconContent		: '<i style="display: inline-block;' +
												'margin: 4px 0 0 1px;' +
												'width: 34px;' +
												'font: 700 15px \'etelka_pro\',Arial,sans-serif;' +
												'color: #fff;">' + ++iconCounter + '</i>',
							img 			: val['img'],
							isPrizmatron	: val['isPrizmatron'],
							address 		: val['address'],
							phone 			: val['phone'],
							free			: val['free']
						},
						// placemark options
						{
							iconLayout: 'default#imageWithContent',
							iconImageHref: iconHref,
							iconImageSize: [36, 44],
							iconOffset: [-10, -40],
							balloonMaxWidth: 200,
							balloonContentLayout:  MyBalloonContentLayoutClass,
							balloonOffset: [0, 5]
						}
					);
					map.geoObjects.add(placemark);
				});
			});
			// link border-list and geoObjects
			$('.border-list li').each(function(){
			 	$(this).click(function(){
			 		var itemIndex = $(this).index();
			 		map.geoObjects.get(itemIndex).balloon.open();
			 	});
			});
		});
	});
	/* ---- end Yandex map ---- */

	/* ------ Fancybox ------ */
	$(".fancybox").fancybox();

})(jQuery);