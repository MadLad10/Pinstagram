"""Place-specific review text for the dev seed.

Each place gets reviews with concrete, checkable details (prices, wifi,
crowds, opening days, problems) and some disagreement, so review summaries and
semantic search have real signal to work with. Businesses are fictional;
landmarks are public places described in general terms.
"""

# Extra fictional reviewers so a place can have more reviews than the core
# demo users (one review per user per place).
REVIEWERS = [
    ("sabbir@pinstagram.app", "Sabbir Ahmed", "Remote worker, always hunting for wifi.", "user"),
    ("mitu@pinstagram.app", "Mitu Sultana", "Weekend explorer with two kids in tow.", "user"),
    ("farhan@pinstagram.app", "Farhan Kabir", "Street food over fine dining, every time.", "user"),
    ("lamia@pinstagram.app", "Lamia Haque", "Architecture student. Sketchbook always open.", "user"),
    ("imran@pinstagram.app", "Imran Hossain", "Business traveller between Dhaka and Ctg.", "user"),
]  # fmt: skip

# place name -> [(rating, body)]
PLACE_REVIEWS: dict[str, list[tuple[int, str]]] = {
    "Lalbagh Fort": [
        (5, "Go right at opening on a weekday, the gardens are almost empty and the light on the red walls is beautiful. Foreigner tickets cost much more than local ones."),
        (4, "Lovely grounds and the Pari Bibi tomb is worth seeing, but the museum section is small and some rooms were closed."),
        (3, "Very crowded on Friday afternoon, with school groups everywhere. Hardly any shade, so bring water."),
        (4, "Rickshaw from Azimpur is easy. Toilets near the entrance were not clean. Still a must for history lovers."),
        (5, "Took my parents in the evening, the fountain area is peaceful and there are benches to sit. Closed on Sundays, check before going."),
    ],
    "Ahsan Manzil": [
        (5, "The museum rooms with the original furniture are fascinating, and the pink facade looks great from the river side."),
        (4, "Photography is not allowed inside, which was disappointing. The ticket queue moved quickly though."),
        (3, "Getting there through Sadarghat traffic took over an hour. The building is impressive but the surrounding area is chaotic and dirty."),
        (4, "Spend at least an hour inside, the history of the Nawabs is well explained in English and Bangla. Closed Thursdays."),
    ],
    "Star Mosque": [
        (5, "The mosaic of Japanese and English china tiles is stunning up close. Caretakers were welcoming to visitors."),
        (4, "Small mosque, you can see everything in twenty minutes. Women should bring a scarf and everyone should dress modestly."),
        (3, "Hard to find in the narrow lanes of Armanitola and no parking at all. Avoid visiting during prayer times."),
        (5, "Best visited in the morning when the star tiles catch the sun. Free entry, but leave a donation."),
    ],
    "Dhakeshwari Temple": [
        (5, "Peaceful and colourful, especially during Durga Puja when the whole compound is decorated."),
        (4, "Shoes must be left at the gate, the stall there keeps them for a small tip. The priests were happy to explain the history."),
        (3, "Extremely crowded during festivals and security checks take time. On a normal day it is calm."),
        (4, "Easy to reach on foot from Palashi crossing. Photography is allowed in the courtyard but not of the main idol."),
    ],
    "National Parliament House": [
        (5, "Louis Kahn's building is breathtaking at golden hour from Crescent Lake. Pure geometry."),
        (4, "You can only go inside with a prior permission letter, so most people just see it from outside. The lawns are great for evening walks."),
        (4, "Security guards stop you from flying drones or using tripods near the fence."),
        (3, "Lovely architecture but there is no shade and no food nearby except street vendors on Manik Mia Avenue."),
        (5, "Cycled around the complex on a Friday morning, the roads are wide and almost empty."),
    ],
    "Hatirjheel Lake": [
        (4, "The evening light show and water taxis are fun. A water taxi from Rampura costs about 30 taka."),
        (3, "The lake water smells bad in the dry season. Better after the monsoon."),
        (5, "Best place in the city for a long walk or cycling, the walkways are wide and well lit at night."),
        (4, "Very busy on weekend evenings and the food stalls are expensive for what you get. Weekday nights are relaxed."),
    ],
    "Dhanmondi Lake": [
        (5, "Shaded walking track all around the lake, perfect for morning jogs. Lots of birds."),
        (4, "Rabindra Sarobar has free cultural shows some evenings. Paddle boats are cheap but often booked out."),
        (4, "Plenty of food stalls with fuchka and chotpoti. Parking near Road 8 is difficult."),
        (3, "Gets noisy and crowded after 5 pm, and some parts of the track are broken."),
        (5, "Great with kids, there is open space and the bridge views at sunset are lovely."),
    ],
    "Ramna Park": [
        (5, "Huge green space right in the middle of the city, quiet early in the morning."),
        (4, "The lake inside is nice and there are exercise groups at dawn. Closes at night."),
        (3, "During Pohela Boishakh it is packed beyond belief, impossible to move. On normal days it is calm."),
        (4, "Clean walking paths and lots of old trees for shade. Toilets are few and not well maintained."),
    ],
    "National Botanical Garden": [
        (5, "Enormous garden with hundreds of tree species, plan half a day. The cactus house is a highlight."),
        (4, "Tickets are cheap and there is parking at the gate, but signs inside are poor and it is easy to get lost."),
        (3, "Mosquitoes everywhere in the evening, bring repellent. Some areas looked neglected."),
        (4, "Combine it with the zoo next door. Mirpur traffic on the way back was terrible."),
    ],
    "Gulshan Lake Park": [
        (5, "Quiet lakeside park, clean and well maintained. Popular with joggers before 8 am."),
        (4, "Nice benches by the water and outdoor seating at the kiosk. Gates close at sunset."),
        (4, "Safe and calm, good for an evening walk with family. Small though, you can cover it in 30 minutes."),
    ],
    "Cafe Mango": [
        (5, "The mango cold brew is as good as everyone says. Sunny window bar, great in the morning."),
        (4, "Wifi is fast and they don't mind if you stay a few hours, but it gets loud after lunch with office crowds."),
        (3, "Coffee is good but expensive, around 350 taka for a cold brew. Seating is limited and the tables are small."),
        (4, "Friendly staff and quick service. The croissants were stale on my visit."),
        (5, "My favourite Banani cafe for a quiet morning read. The AC works well even in summer."),
    ],
    "Banani Book Cafe": [
        (5, "Cardamom latte and a shelf of second-hand books, what more do you need. Very quiet on weekdays."),
        (4, "Great board game collection, we played for three hours and nobody rushed us."),
        (4, "Wifi works but slows down in the evening. Power sockets only near the window tables."),
        (3, "The food menu is small and the pasta was bland. Come for coffee and books, not meals."),
        (5, "Cozy reading corners and soft music. A good place to work on a laptop in the afternoon."),
    ],
    "Uttara Bean Co.": [
        (5, "Proper specialty coffee: single-origin pour-overs and they explain the beans. Best coffee in Uttara."),
        (4, "Spacious with plenty of parking, which is rare. Wifi is reliable for video calls."),
        (4, "Prices are high, a pour-over is 400 taka, but the quality justifies it."),
        (3, "Far from central Dhaka, it took 90 minutes from Dhanmondi. Pastries are average."),
        (5, "Quiet and bright, I work here twice a week. The baristas are knowledgeable."),
    ],
    "Tong Tea Corner": [
        (5, "Malai cha for 30 taka and hot singara, the real Dhaka experience. Open till late."),
        (4, "Great adda spot with friends after work, but it is a street stall so expect traffic noise and smoke."),
        (3, "No proper seating, just benches by the road. Hygiene is questionable."),
        (4, "Cheapest good tea in Karwan Bazar. Gets crowded around 7 pm."),
    ],
    "Kacchi Ghor": [
        (5, "The mutton kacchi is tender and fragrant, and the potatoes are perfect. The borhani is excellent too."),
        (4, "Generous portions for the price, a full plate is about 380 taka. Expect a 20 minute wait on Fridays."),
        (3, "Food is good but the AC was barely working and the tables were cramped."),
        (4, "Ordered a family platter for six, enough food and very reasonably priced."),
        (5, "Best kacchi in Dhanmondi in my opinion. Go before 1 pm to avoid the queue."),
    ],
    "Old Dhaka Biryani House": [
        (5, "Haji-style beef biryani cooked in mustard oil and served on leaf plates. Authentic and cheap, about 200 taka a plate."),
        (4, "The lane is very narrow and there is no parking, take a rickshaw from Gulistan. Worth the effort for the biryani."),
        (4, "The borhani is spicy and refreshing. Seating is basic and it gets hot inside, there is no AC."),
        (3, "Biryani sells out by 3 pm, we arrived at 4 and only got the last few plates. Come early."),
        (5, "Old Dhaka food at its best. Combine it with a walk to Star Mosque nearby."),
    ],
    "Mezban Bari": [
        (5, "Real Chittagonian mezban beef, spicy and rich. The kala bhuna is a must."),
        (4, "Family-style seating and big portions. It gets very loud with large groups."),
        (4, "The AC dining room is comfortable. Prices are fair, around 300 taka per person."),
        (3, "Too spicy for my kids and there are no mild options. Service was slow on a busy Friday."),
    ],
    "Lakeview Rooftop": [
        (5, "Sunset over Gulshan Lake from the rooftop is spectacular. The mocktails are creative."),
        (3, "Very expensive, 600 taka for a mocktail, and the music is loud after 8 pm. Not a place for a quiet conversation."),
        (4, "Great for a date or a celebration. Book a lake-facing table in advance on weekends."),
        (4, "Wifi is available but slow. Service was attentive. Food portions are small for the price."),
    ],
    "Hotel Shapla Grand": [
        (4, "Clean rooms and a nice rooftop pool. Five minutes walk to Karwan Bazar metro station."),
        (5, "The breakfast buffet is huge with both Bangladeshi and continental options. Staff were very helpful."),
        (3, "Rooms facing the main road are noisy, ask for one at the back. Wifi was patchy on higher floors."),
        (4, "Good business hotel with a meeting room and parking. Expensive compared to similar hotels."),
    ],
    "Airport Garden Inn": [
        (4, "The free airport shuttle worked perfectly for my early flight. Rooms are simple but clean."),
        (4, "Good value stopover hotel, about 15 minutes from the airport even with traffic."),
        (3, "Thin walls and you can hear planes at night. Breakfast was basic."),
        (5, "Staff arranged a free late checkout and the wifi was fast enough for work calls."),
    ],
    "Cloud Nine Rooftop Cafe": [
        (5, "Rooftop with fairy lights and a view over Dhanmondi Lake. Quiet on weekday afternoons and the wifi is fast enough for work."),
        (4, "The pour-over coffee is excellent. Weekend evenings get busy and noisy with birthday groups."),
        (4, "Lovely place to work in the morning, with plenty of plugs along the parapet tables. No AC on the roof, so it gets hot on summer afternoons."),
        (3, "The lift is often broken and it is five flights of stairs. Prices are a bit high, a latte is 280 taka."),
        (5, "My go-to calm spot in Dhanmondi. The sunset from the roof is beautiful."),
    ],
    "Paper & Pour": [
        (5, "Strict quiet zone upstairs, like a library with coffee. Perfect for studying or working on a laptop."),
        (4, "Cheap coffee, a cappuccino is 180 taka, and you can sit for hours. Wifi is stable."),
        (4, "Long tables with power outlets everywhere. Downstairs is louder with group conversations."),
        (3, "Very limited food, mostly sandwiches. Gets full with students during exam season."),
    ],
    "Chankharpul Kebab House": [
        (5, "Charcoal sheek kebabs and boti with fresh naan, smoky and juicy. Open until late at night."),
        (4, "Cheap and delicious, a full meal is about 250 taka. Seating is basic plastic chairs."),
        (3, "Smoke from the grill fills the seating area. Great food, but no AC and no parking."),
        (4, "Best late-night food in Old Dhaka. Try the chicken chaap with lassi."),
    ],
    "Puran Dhaka Tehari Ghar": [
        (5, "Beef tehari cooked in mustard oil and served on banana leaves. Rich and cheap, around 150 taka."),
        (4, "Morning tehari here is a ritual for locals. It comes with a green chili and onion salad."),
        (3, "Very small place, you will share a table with strangers. Sells out early."),
        (4, "Authentic Old Dhaka flavour, a bit oily for some. The tehari is best before noon."),
    ],
    "Mirpur Social Cafe": [
        (4, "Big group tables and board games, great for hanging out with friends near Mirpur 10."),
        (4, "Wifi and AC work well and there is parking, which is rare in Mirpur. The coffee is average though."),
        (3, "Very loud in the evenings with student groups, not a place to work."),
        (5, "Their cheesecake is excellent. Two minutes walk from the Mirpur 10 roundabout."),
    ],
}  # fmt: skip
