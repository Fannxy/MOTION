add_executable(crosstabs_shared crosstabs_shared_main.cpp common/crosstabs_shared.cpp)

if (NOT MOTION_BUILD_BOOST_FROM_SOURCES)
    find_package(Boost
            COMPONENTS
            program_options
            REQUIRED)
endif ()

target_link_libraries(crosstabs_shared
        MOTION::motion
        Boost::program_options
        )
